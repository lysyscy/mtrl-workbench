"""集中硬编码：信息化系统门户/服务地址与登录账号。

改信息化系统地址或账号时只需改这一处，其余模块统一 `from consts import ...` 引用。
"""

PORTAL_URL = 'http://106.46.169.212:30785/ngweb/portal/index.html'
BASE_URL = 'http://106.46.169.212:30785'
LOGIN_USER = 'SCY980803'  # 信息化系统账号
