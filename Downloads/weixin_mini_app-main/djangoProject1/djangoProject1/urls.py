"""
URL configuration for djangoProject1 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from app01.views import index
from django.views.static import serve
from django.conf import settings
from app01.views import CustomTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView
urlpatterns = [
    path('admin/', admin.site.urls),
    path('index/', index),
    path('app01/', include('app01.urls')),
    path('media/<path:path>', serve,{'document_root': settings.MEDIA_ROOT}),
    path('api/', include('app01.urls')),  # 假设app01有单独的urls.py
    # JWT Token接口
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),  # 获取Token
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # 刷新Token

]