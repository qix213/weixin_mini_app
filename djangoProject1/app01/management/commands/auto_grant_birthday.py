import os
import traceback
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
from django.conf import settings

# 注意：请确保这里的 app01 换成你实际的 app 名称
from app01.models import User, Coupon, UserCoupon

class Command(BaseCommand):
    help = '每月自动执行：给当月生日的正式会员发放 200 元代金券'

    def handle(self, *args, **options):
        # 定义日志文件路径 (存放在你的 Django 项目根目录下)
        log_file = os.path.join(settings.BASE_DIR, 'birthday_cron.log')

        # 🌟 顺应 Windows 原生编码，使用 GBK 写入
        def write_log(message):
            with open(log_file, 'a', encoding='gbk', errors='ignore') as f:
                f.write(message + '\n')

        current_month = timezone.now().month
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        write_log(f"[{now_str}] ===========================================")
        write_log(f"[*] 开始执行 {current_month}月 生日礼券自动下发任务...")

        try:
            # 1. 获取或创建 200元 面值的生日代金券模板
            birthday_coupon, _ = Coupon.objects.get_or_create(
                title="生日专属200元代金券",
                defaults={
                    'coupon_type': 1,
                    'money': 200.00,
                    'discount_rate': 1.00,
                    'min_consume': 0.00,
                    'valid_days': 30,
                    'is_active': True
                }
            )

            # 2. 筛选当月生日，且星级在 1星(含) 以上的正式会员
            birthday_users = User.objects.filter(
                birth_date__isnull=False,
                birth_date__month=current_month,
                user_type__gte=2
            )

            grant_count = 0
            already_granted_count = 0

            # 3. 遍历发券
            for user in birthday_users:
                has_granted = UserCoupon.objects.filter(
                    user=user,
                    coupon=birthday_coupon,
                    start_time__month=current_month,
                    start_time__year=timezone.now().year
                ).exists()

                if not has_granted:
                    UserCoupon.objects.create(
                        user=user,
                        coupon=birthday_coupon,
                        start_time=timezone.now(),
                        end_time=timezone.now() + timedelta(days=birthday_coupon.valid_days),
                        is_used=False
                    )
                    grant_count += 1
                else:
                    already_granted_count += 1

            # 4. 成功日志
            msg = f"[SUCCESS] 任务完成！符合条件: {birthday_users.count()}人。成功新发: {grant_count}张，跳过已发: {already_granted_count}人。"
            write_log(msg)

        except Exception as e:
            # 捕获报错并写入日志
            err_msg = f"[ERROR] 任务执行崩溃: {str(e)}\n{traceback.format_exc()}"
            write_log(err_msg)

        write_log(f"===========================================================\n")