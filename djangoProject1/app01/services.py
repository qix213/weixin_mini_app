from .models import (RechargeOrder, UserWallet, WalletTransaction,
    User, CommissionRecord, Order, OrderItem, UserCoupon, Coupon)
import datetime
import traceback
import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

def calculate_and_grant_commission(order):
    print(f"\n========== 【复杂商品分佣调试 探照灯】 ==========")
    print(f"触发的订单号: {order.order_sn}")

    buyer = order.user
    if not buyer:
        print("❌ 失败原因：该订单没有关联购买用户 (order.user 为空)")
        print("=========================================\n")
        return

    parent = buyer.parent_user
    if not parent:
        print(f"❌ 失败原因：购买用户 [{buyer.phone}] 没有上级推荐人")
        print("=========================================\n")
        return

    print(f"找到上级推荐人: {parent.phone} (ID: {parent.id}, 星级: {parent.user_type})")

    # 🌟 规则 5：拦截没有佣金资格的用户
    if parent.user_type not in [3, 4]:
        print(f"❌ 失败原因：上级用户星级为 {parent.user_type}，不享受任何佣金返点权益")
        print("=========================================\n")
        return

    # 取出之前在模型里定义好的真金白银基数（已自动去除了 coupon 的水分，包含了 wallet）
    commission_base = Decimal(str(order.commission_base or 0))
    order_total = Decimal(str(order.total_price or 0))

    if commission_base <= 0 or order_total <= 0:
        print("❌ 失败原因：该订单全额使用代金券或积分为0元购，无真金白银流水，不予发佣")
        print("=========================================\n")
        return

    total_commission = Decimal('0.00')
    print(f"订单总价: {order_total}，实际返佣大盘基数(扣除代金券后): {commission_base}")

    # 遍历订单里的每一个商品，按商品类型和分摊金额精确算佣
    for item in order.items.all():
        # 💡 注意：这里假设你的 OrderItem 关联了 Goods 表。
        # 如果你的 item 直接有 goods_type 字段，请改成 item.goods_type
        goods_type = item.goods.goods_type
        item_total = Decimal(str(item.total_price))

        # 【核心算法】：按该商品占订单总金额的比例，分摊真实的返佣基数
        # 比如商品A占订单总价的60%，那它就分摊 60% 的 commission_base
        item_real_pay = (item_total / order_total) * commission_base

        rate = Decimal('0.00')

        # 🌟 规则 3：蓝朋友2星 (user_type=3)，只有居家产品 (1) 返 10%
        if parent.user_type == 3:
            if goods_type == 1:
                rate = Decimal('0.10')

        # 🌟 规则 4：蓝朋友3星 (user_type=4)
        elif parent.user_type == 4:
            # 🚨 核心修复：在这里只发 居家产品(1) 的 15% 佣金！
            # 线下项目(2) 绝对不能在这里发，必须等后续到店核销时再发！
            if goods_type == 1:
                rate = Decimal('0.15')
            elif goods_type == 2:
                print(f"  -> 商品 [{item.goods_name}](类型2): 线下项目，购买时暂不返佣，等待核销时自动发放")
                rate = Decimal('0.00')  # 强制归零，防止错发

        # 如果该商品符合上级的返佣政策，进行累加
        if rate > 0:
            item_commission = item_real_pay * rate
            total_commission += item_commission
            print(
                f"  -> 商品 [{item.goods_name}](类型{goods_type}): 占比实付 {item_real_pay:.2f} * {rate * 100}% = 佣金 {item_commission:.2f}")
        else:
            print(f"  -> 商品 [{item.goods_name}](类型{goods_type}): 不参与当前星级的返佣")

    # 最终四舍五入保留两位小数
    final_commission_amount = round(total_commission, 2)
    print(f"最终核算总佣金: {final_commission_amount}")

    if final_commission_amount <= 0:
        print("❌ 失败原因：订单内没有符合该上级返点政策的商品")
        print("=========================================\n")
        return

    # ================= 写入数据库的事务操作 =================
    try:
        with transaction.atomic():
            locked_parent = User.objects.select_for_update().get(id=parent.id)
            locked_parent.withdrawable_balance += final_commission_amount
            locked_parent.save(update_fields=['withdrawable_balance'])

            buyer_name = buyer.nickname if buyer.nickname else (buyer.phone if buyer.phone else "未知用户")
            desc_text = f"来自下级会员[{buyer_name}]的特定商品消费奖励"

            # 写入佣金记录模型
            CommissionRecord.objects.create(
                user=locked_parent,
                buyer=buyer,
                order=order,
                amount=final_commission_amount,
                desc=desc_text
            )
            print(f"✅ 成功！已给 {locked_parent.phone} 发放可提现佣金: +{final_commission_amount}元")

    except Exception as e:
        print(f"❌ 写入数据库时发生异常: {str(e)}")

    print("=========================================\n")


def calculate_offline_commission(record, asset):
    """
    🌟 线下项目专属：单次核销分佣算法 (引入优惠券剔除与星级判定)
    触发时机：用户在前端点击“确认服务/确认核销”后
    """
    print(f"\n========== 【线下项目单次核销分佣 探照灯】 ==========")

    buyer = record.user
    parent = buyer.parent_user

    if not parent:
        print(f"❌ 失败原因：购买用户 [{buyer.phone}] 没有上级推荐人，无需计算佣金")
        print("=========================================\n")
        return

    # 🚨 致命拦截：检查上级会员是否已经过期！
    if not parent.is_valid_vip:
        print(f"❌ 失败原因：上级推荐人 [{parent.phone}] 会员已过期 (到期时间: {parent.expire_time})，停止发佣！")
        if parent.user_type > 1:
            parent.user_type = 1
            parent.save(update_fields=['user_type'])
        print("=========================================\n")
        return

    # 🌟 核心规则拦截：只有 蓝朋友3星(user_type=4) 才有线下项目(goods_type=2)的返佣资格！
    if parent.user_type != 4:
        print(f"❌ 失败原因：上级会员星级为 {parent.user_type}，不满足线下项目返佣条件 (仅限4档会员)")
        print("=========================================\n")
        return

    # 1. 顺藤摸瓜：找到原始订单
    real_order = Order.objects.filter(
        user=asset.user,
        status__in=[1, 2, 3],  # 找已经付款的有效订单
        items__goods=asset.project  # 精准匹配这个订单里买了这个线下项目
    ).order_by('-create_time').first()

    if not real_order:
        print(f"❌ 严重警告：找不到资产 {asset.id} 对应的真实支付订单，无法核算分佣金额！跳过分佣。")
        return

    order_sn = real_order.order_sn
    print(f"✅ 成功反查到真实的原始订单号: {order_sn}")

    # 获取商品明细
    order_item = OrderItem.objects.filter(order=real_order, goods=asset.project).first()
    if not order_item:
        print(f"❌ 失败原因：未在订单 {order_sn} 中找到商品 {asset.project.name} 的明细")
        return

    # 2. 🌟 提取核心计算数据，使用财务分摊算法剔除优惠券水分
    commission_base = Decimal(str(real_order.commission_base or 0))  # 订单整单的真金白银
    order_total = Decimal(str(real_order.total_price or 0))  # 订单总价
    item_total = Decimal(str(order_item.total_price or 0))  # 本项目总价

    if commission_base <= 0 or order_total <= 0:
        print("❌ 失败原因：该订单全额使用代金券或0元购，无真金白银流水，不予发佣")
        print("=========================================\n")
        return

    # 【分摊算法】：算出该线下项目真实花掉的"真金白银"
    item_real_pay = (item_total / order_total) * commission_base
    total_times = Decimal(str(asset.total_times))

    if total_times <= 0:
        print("❌ 失败原因：该资产总次数异常 (<=0)")
        return

    # 3. 核心公式： (项目真金价值 / 总次数) * 15%
    per_time_real_money = item_real_pay / total_times
    commission_rate = Decimal('0.15')  # 🌟 规则：蓝朋友3星享受线下项目15%的佣金

    # 四舍五入保留两位小数
    commission_amount = round(per_time_real_money * commission_rate, 2)

    print(f"订单总价: {order_total} | 订单真金基数: {commission_base}")
    print(f"本项目原价: {item_total} | 本项目真金分摊: {item_real_pay:.2f}")
    print(f"总核销次数: {total_times} | 单次核销真金价值: {per_time_real_money:.2f}")
    print(f"计算公式: {per_time_real_money:.2f} * 15% = {commission_amount}")

    if commission_amount <= 0:
        print("❌ 失败原因：计算出的单次佣金 <= 0，停止发佣")
        print("=========================================\n")
        return

    # 4. 原子化发钱
    try:
        with transaction.atomic():
            locked_parent = User.objects.select_for_update().get(id=parent.id)
            locked_parent.withdrawable_balance += commission_amount
            locked_parent.save(update_fields=['withdrawable_balance'])

            buyer_name = buyer.nickname if buyer.nickname else (buyer.phone if buyer.phone else "未知用户")
            desc_text = f"下级[{buyer_name}]核销线下项目({asset.project.name})单次佣金"

            # 写入佣金流水表
            CommissionRecord.objects.create(
                user=locked_parent,
                buyer=buyer,
                order=real_order,
                amount=commission_amount,
                desc=desc_text
            )
            print(f"✅ 成功！已给上级 {locked_parent.phone} (蓝朋友3星) 发放单次核销佣金: +{commission_amount}元")

    except Exception as e:
        print(f"❌ 写入数据库发生异常: {str(e)}")

    print("=========================================\n")


def pay_order_with_wallet(user, order_sn):
    """
    纯电子账户支付核心逻辑（全额钱包支付）
    如果需要混合支付（钱包+微信），逻辑类似，只需传入实际需要从钱包扣的金额即可。
    """
    try:
        # ==============================================================
        # 1. 开启原子事务：一损俱损，一荣俱荣，绝不能出现钱扣了订单没变
        # ==============================================================
        with transaction.atomic():

            # 🌟 2. 悲观锁锁定订单：防止同一笔订单被多线程并发支付
            order = Order.objects.select_for_update().get(
                order_sn=order_sn,
                user=user,
                status=0  # 必须是待付款状态
            )

            # 计算订单还需要付多少钱（已排除了积分和优惠券）
            need_pay_amount = order.total_price - order.point_deduct_money - order.coupon_deduct

            if need_pay_amount <= 0:
                raise Exception("订单金额异常，无需支付")

            # 🌟 3. 悲观锁锁定钱包：极其重要！防止用户一边买东西一边提现导致余额穿透
            wallet = UserWallet.objects.select_for_update().get(user=user)

            if not wallet.status:
                raise Exception("电子账户已被冻结，无法支付")

            if wallet.total_balance < need_pay_amount:
                raise Exception(f"电子账户余额不足（当前:{wallet.total_balance}，需支付:{need_pay_amount}）")

            # ==============================================================
            # 4. 🌟 核心财务算法：优先扣除赠送金，不足部分扣除本金
            # ==============================================================
            bonus_deduct = Decimal('0.00')
            principal_deduct = Decimal('0.00')

            if wallet.bonus >= need_pay_amount:
                # 赠送金足够支付全款
                bonus_deduct = need_pay_amount
            else:
                # 赠送金不够，全扣光，剩下的用本金补
                bonus_deduct = wallet.bonus
                principal_deduct = need_pay_amount - wallet.bonus

            # 5. 更新钱包余额快照
            wallet.bonus -= bonus_deduct
            wallet.principal -= principal_deduct
            wallet.total_balance = wallet.principal + wallet.bonus
            wallet.save(update_fields=['bonus', 'principal', 'total_balance', 'update_time'])

            # ==============================================================
            # 6. 生成资金流水（财务对账的铁证）
            # ==============================================================
            trade_no = f"WAL{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"

            WalletTransaction.objects.create(
                wallet=wallet,
                trade_no=trade_no,
                order_sn=order.order_sn,
                transaction_type=2,  # 2: 消费扣款
                amount=-need_pay_amount,  # 支出为负数
                principal_change=-principal_deduct,
                bonus_change=-bonus_deduct,
                after_balance=wallet.total_balance,
                remark=f"支付商城订单: {order.order_sn}"
            )

            # ==============================================================
            # 7. 更新订单状态与资金拆分结构（决定了后续的分佣金额）
            # ==============================================================
            order.wallet_pay = need_pay_amount
            order.wechat_pay = Decimal('0.00')
            order.commission_base = need_pay_amount  # 🌟 钱包付的钱，全额算入返佣基数！

            order.actual_pay_money = need_pay_amount
            order.pay_method = 4  # 4: 电子账户支付
            order.pay_no = trade_no
            order.pay_time = timezone.now()

            # 状态流转：如果是快递发货则变为 1(待发货)，如果是到店自取则为 1(待取货)
            order.status = 1

            order.save(update_fields=[
                'wallet_pay', 'wechat_pay', 'commission_base', 'actual_pay_money',
                'pay_method', 'pay_no', 'pay_time', 'status'
            ])

        # 走出 with block，事务完美提交
        return True, "支付成功"

    except Order.DoesNotExist:
        return False, "订单不存在或已支付"
    except UserWallet.DoesNotExist:
        return False, "用户未开通电子账户"
    except Exception as e:
        # 如果抛出异常，整个事务回滚，钱和订单都不会变
        return False, str(e)


def handle_recharge_success(order_sn, transaction_id=""):
    """
    处理充值成功核心逻辑：加本金、记流水、批量发代金券
    """
    try:
        with transaction.atomic():
            # 1. 锁订单防重复
            order = RechargeOrder.objects.select_for_update().get(order_sn=order_sn)
            if order.status == 1:
                return True, "订单已处理，无需重复充值"

            order.status = 1
            order.pay_time = timezone.now()
            order.transaction_id = transaction_id
            order.save(update_fields=['status', 'pay_time', 'transaction_id'])

            # 2. 锁钱包加本金
            wallet, _ = UserWallet.objects.select_for_update().get_or_create(user=order.user)

            # 因为这次规则不送余额，所以 bonus_add 是 0，只加 principal 本金
            wallet.principal += order.amount
            wallet.total_balance = wallet.principal + wallet.bonus
            wallet.save(update_fields=['principal', 'total_balance', 'update_time'])

            # 3. 记财务流水账
            trade_no = f"IN{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
            WalletTransaction.objects.create(
                wallet=wallet,
                trade_no=trade_no,
                order_sn=order.order_sn,
                transaction_type=1,  # 1: 充值
                amount=order.amount,
                principal_change=order.amount,
                bonus_change=Decimal('0.00'),
                after_balance=wallet.total_balance,
                remark=f"参与储值套餐: {order.activity.name}"
            )

            # =========================================================
            # 🌟 4. 根据规则下发代金券 (980发1张，3980发3张，9800发6张)
            # =========================================================
            if order.activity and order.activity.gift_coupon and order.activity.gift_coupon_num > 0:
                coupon_template = order.activity.gift_coupon

                # 批量生成券发给用户，降低数据库写入压力
                coupons_to_create = [
                    UserCoupon(
                        user=order.user,
                        coupon=coupon_template,
                        start_time=timezone.now(),
                        end_time=timezone.now() + datetime.timedelta(days=coupon_template.valid_days),
                        is_used=False
                    )
                    for _ in range(order.activity.gift_coupon_num)
                ]
                UserCoupon.objects.bulk_create(coupons_to_create)

        return True, "充值成功，代金券已发放至卡包"

    except RechargeOrder.DoesNotExist:
        return False, "充值订单不存在"
    except Exception as e:
        traceback.print_exc()
        return False, f"充值入账异常：{str(e)}"

def grant_member_assets(user, target_level, amount_paid, remark_text="会员资产入账"):
    """
    🌟 通用会员资产与权益累加引擎（支持注册与老用户升级）
    :param user: 用户模型对象
    :param target_level: 目标会员等级 (2:1星, 3:2星, 4:3星)
    :param amount_paid: 本次实际充值/支付的金额 (Decimal)
    :param remark_text: 流水账备注
    """
    # 1. 动态匹配每档升级应该获得的 100 元代金券张数
    # 980(1星)->1张，3980(2星)->3张，9800(3星)->6张
    LEVEL_COUPON_MAP = {2: 1, 3: 3, 4: 6}
    coupon_num = LEVEL_COUPON_MAP.get(int(target_level), 0)

    try:
        with transaction.atomic():
            # =======================================================
            # 核心 1：电子钱包余额安全“累加” (绝杀浮点数冲突)
            # =======================================================
            wallet, _ = UserWallet.objects.select_for_update().get_or_create(user=user)

            amount_decimal = Decimal(str(amount_paid or '0.00'))
            if amount_decimal > 0:
                current_principal = Decimal(str(wallet.principal or '0.00'))
                current_bonus = Decimal(str(wallet.bonus or '0.00'))

                # 累加本金
                wallet.principal = current_principal + amount_decimal
                wallet.total_balance = wallet.principal + current_bonus
                wallet.save(update_fields=['principal', 'total_balance', 'update_time'])

                # 记录钱包流水
                trade_no = f"VIP{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
                WalletTransaction.objects.create(
                    wallet=wallet,
                    trade_no=trade_no,
                    transaction_type=1,  # 1: 充值/转入
                    amount=amount_decimal,
                    principal_change=amount_decimal,
                    bonus_change=Decimal('0.00'),
                    after_balance=wallet.total_balance,
                    remark=remark_text
                )
                print(f"💰 [资产累加] 已成功为用户 {user.phone} 叠加钱包余额: +￥{amount_decimal}")

            # =======================================================
            # 核心 2：代金券直接“累加”印发
            # =======================================================
            if coupon_num > 0:
                coupon_template, _ = Coupon.objects.get_or_create(
                    title="储值专享100元代金券",
                    defaults={
                        'coupon_type': 1, 'money': 100.00, 'discount_rate': 1.00,
                        'min_consume': 0.00, 'valid_days': 365, 'is_active': True
                    }
                )

                # 循环创建，直接累加塞进用户的卡包
                for _ in range(coupon_num):
                    UserCoupon.objects.create(
                        user=user,
                        coupon=coupon_template,
                        start_time=timezone.now(),
                        end_time=timezone.now() + timedelta(days=coupon_template.valid_days),
                        is_used=False
                    )
                print(f"🎫 [资产累加] 已成功为用户 {user.phone} 额外叠发 100元代金券: {coupon_num} 张")

            # =======================================================
            # 核心 3：更新会员等级与一年有效期
            # =======================================================
            user.user_type = target_level
            user.expire_time = timezone.now() + timedelta(days=365)
            user.save(update_fields=['user_type', 'expire_time'])
            print(f"👑 [身份变更] 用户 {user.phone} 等级已变更为: {target_level}，有效期顺延一年")

            return True, "资产累加成功"

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [资产累加失败] 用户 {user.phone}: {str(e)}")
        return False, str(e)