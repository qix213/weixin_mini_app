from django import forms
from .models import Order, ExpressLogistics

class ExpressCreateForm(forms.Form):
    """新建运单表单：选择订单 + 输入运单号"""
    # 订单下拉框（仅显示快递配送、未取消的订单）
    order = forms.ModelChoiceField(
        queryset=Order.objects.filter(
            delivery_type=1,  # 仅快递配送订单
            status__in=[0,1,2,3],  # 排除已取消订单
            is_delete=False
        ).order_by("-create_time"),
        label="关联订单",
        empty_label="请选择订单",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    # 运单号输入框（支持多个运单号，用逗号分隔）
    logistics_no = forms.CharField(
        label="运单号",
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "多个运单号用逗号分隔，如：444003077898,441003077850"})
    )
    # 物流公司（默认顺丰）
    logistics_company = forms.CharField(
        label="物流公司",
        max_length=32,
        initial="顺丰速运",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    def clean_logistics_no(self):
        """清洗运单号：去空格、拆分多个运单号"""
        logistics_no = self.cleaned_data.get("logistics_no")
        # 拆分多个运单号（逗号/空格分隔）
        logistics_no_list = [no.strip() for no in logistics_no.replace("，", ",").split(",") if no.strip()]
        if not logistics_no_list:
            raise forms.ValidationError("请输入有效的运单号")
        return logistics_no_list