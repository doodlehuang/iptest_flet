import flet as ft
import aiohttp
import asyncio
import json
from bs4 import BeautifulSoup
import datetime

class AsyncWorker:
    def __init__(self):
        self.session = None

    async def create_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def get_ip_info(self):
        await self.create_session()
        try:
            async with self.session.get('https://4.ipw.cn', timeout=2) as response:
                domestic_ip = await response.text()
                domestic_ip = domestic_ip.strip()

            async with self.session.get('http://ip-api.com/line?fields=query', timeout=2) as response:
                foreign_ip = await response.text()
                foreign_ip = foreign_ip.strip()

            async def get_ip_details(ip):
                async with self.session.get(f'http://ip-api.com/json/{ip}') as response:
                    return await response.json()

            domestic_ip_info = await get_ip_details(domestic_ip)
            foreign_ip_info = await get_ip_details(foreign_ip)

            if domestic_ip == foreign_ip:
                return {"ip": domestic_ip, "region": f'{domestic_ip_info["regionName"]}, {domestic_ip_info["country"]}'}
            else:
                return {
                    "domestic_ip": domestic_ip,
                    "domestic_region": f'{domestic_ip_info["regionName"]}, {domestic_ip_info["country"]}',
                    "foreign_ip": foreign_ip,
                    "foreign_region": f'{foreign_ip_info["regionName"]}, {foreign_ip_info["country"]}'
                }
        except Exception as e:
            return {"error": f"获取IP地址时出现错误: {e}"}

    async def check_network_freedom(self):
        urls = [
            'https://www.v2ex.com/generate_204',
            'https://www.youtube.com/generate_204',
            'https://am.i.mullvad.net/ip'
        ]
        success_count = 0

        for url in urls:
            for _ in range(2):
                try:
                    async with self.session.get(url, timeout=0.5) as response:
                        if response.status in [204, 200]:
                            success_count += 1
                            break
                except:
                    continue

        return f"自由（{success_count}/{len(urls)}）" if success_count >= 2 else "受限"

    async def extract_prefdomain_url(self):
        try:
            async with self.session.get('https://www.google.com') as response:
                content = await response.text()
            soup = BeautifulSoup(content, 'html.parser')
            link = soup.find('a', href=lambda href: href and 'setprefdomain' in href)

            if link:
                href = link['href']
                domain = href.split('//')[1].split('/')[0]
                prefdom = href.split('=')[1].split('&')[0]
                if domain == 'www.google.com.hk' and prefdom == 'US':
                    return 'CN'
                else:
                    return prefdom
            return "全球"
        except Exception:
            return "获取Google地区时出现错误"

    async def raw_githubusercontent_speed_test(self):
        try:
            start = datetime.datetime.now()
            async with self.session.head('https://raw.githubusercontent.com', timeout=2) as response:
                end = datetime.datetime.now()
                time_without_proxy = (end - start).total_seconds() * 1000
                return f"{time_without_proxy:.2f} 毫秒"
        except Exception as e:
            return f"GitHub连接测试出错: {e}"

    async def get_auto_login_name(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            async with self.session.get('https://login.cnki.net/TopLogin/api/loginapi/IpLoginFlush', headers=headers) as response:
                text = await response.text()
                result = json.loads(text[1:-1])
                if result.get('IsSuccess'):
                    return result.get('ShowName')
                return None
        except Exception:
            return None

    async def run_all_checks(self):
        results = {
            "ip_info": await self.get_ip_info(),
            "network_status": await self.check_network_freedom(),
            "google_region": await self.extract_prefdomain_url(),
            "github_speed": await self.raw_githubusercontent_speed_test(),
            "academic_name": await self.get_auto_login_name()
        }
        await self.close_session()
        return results

async def main(page: ft.Page):
    page.title = "网络状态检测工具"
    page.window_width = 800
    page.window_height = 800
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20

    # 创建显示控件
    ip_info = ft.Text(size=16, selectable=True)
    network_status = ft.Text(size=16)
    google_region = ft.Text(size=16)
    github_speed = ft.Text(size=16)
    academic_info = ft.Text(size=16)
    progress_ring = ft.ProgressRing(visible=False)

    # 用于存储IP信息的变量
    ip_data = {}
    show_full_ip = False

    def mask_ip(ip):
        parts = ip.split('.')
        return '.'.join(parts[:2] + ['*', '*'])

    def update_ip_display():
        if "error" in ip_data:
            ip_info.value = ip_data["error"]
        else:
            if "ip" in ip_data:
                ip_display = ip_data['ip'] if show_full_ip else mask_ip(ip_data['ip'])
                ip_info.value = f"IP地址：{ip_display}（{ip_data['region']}）"
            else:
                domestic_ip_display = ip_data['domestic_ip'] if show_full_ip else mask_ip(ip_data['domestic_ip'])
                foreign_ip_display = ip_data['foreign_ip'] if show_full_ip else mask_ip(ip_data['foreign_ip'])
                ip_info.value = f"IP地址（面向国内网站）：{domestic_ip_display}（{ip_data['domestic_region']}）\n" \
                               f"IP地址（面向国外网站）：{foreign_ip_display}（{ip_data['foreign_region']}）"
        page.update()

    def toggle_ip_display(e):
        nonlocal show_full_ip
        if ip_data:
            show_full_ip = not show_full_ip
            update_ip_display()

    def copy_ip_to_clipboard(e):
        if "ip" in ip_data:
            page.set_clipboard(ip_data['ip'])
        else:
            page.set_clipboard(f"国内IP: {ip_data['domestic_ip']}, 国外IP: {ip_data['foreign_ip']}")
        page.show_snack_bar(ft.SnackBar(content=ft.Text("IP地址已复制到剪贴板")))

    async def refresh_data(e):
        # 禁用刷新按钮并显示进度环
        refresh_btn.disabled = True
        progress_ring.visible = True
        page.update()

        # 更新所有状态文本为"正在刷新..."
        ip_info.value = "获取IP信息中..."
        network_status.value = "正在刷新..."
        google_region.value = "正在刷新..."
        github_speed.value = "正在刷新..."
        academic_info.value = "正在刷新..."
        page.update()

        # 创建worker并运行检查
        worker = AsyncWorker()
        results = await worker.run_all_checks()

        # 更新显示结果
        nonlocal ip_data
        ip_data = results["ip_info"]
        update_ip_display()
        
        network_status.value = f"网络访问状态：{results['network_status']}"
        google_region.value = f"Google地区：{results['google_region']}"
        github_speed.value = f"GitHub连接速度：{results['github_speed']}"
        academic_name = results['academic_name']
        academic_info.value = f"学术机构：{academic_name if academic_name else '未登录'}"

        # 重新启用刷新按钮并隐藏进度环
        refresh_btn.disabled = False
        progress_ring.visible = False
        page.update()

    # 创建按钮
    refresh_btn = ft.ElevatedButton(
        "刷新",
        on_click=refresh_data,
        bgcolor="#2E7D32",  # GREEN_600
        color="white"
    )

    toggle_ip_btn = ft.ElevatedButton(
        "切换IP显示模式",
        on_click=toggle_ip_display,
        bgcolor="#1565C0",  # BLUE_600
        color="white"
    )

    copy_ip_btn = ft.ElevatedButton(
        "复制IP地址",
        on_click=copy_ip_to_clipboard,
        bgcolor="#1565C0",  # BLUE_600
        color="white"
    )

    # 构建界面
    page.add(
        ft.Column(
            controls=[
                ft.Text("网络状态检测工具", size=30, weight=ft.FontWeight.BOLD),
                ft.Row([progress_ring], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(
                    content=ft.Column([
                        ip_info,
                        ft.Row([toggle_ip_btn, copy_ip_btn])
                    ]),
                    border=ft.border.all(1, "#BDBDBD"),  # GREY_400
                    border_radius=10,
                    padding=10
                ),
                ft.Container(
                    content=ft.Column([
                        network_status,
                        google_region,
                        github_speed,
                        academic_info
                    ]),
                    border=ft.border.all(1, "#BDBDBD"),  # GREY_400
                    border_radius=10,
                    padding=10
                ),
                ft.Row([refresh_btn], alignment=ft.MainAxisAlignment.CENTER)
            ],
            spacing=20
        )
    )

    # 初始刷新
    await refresh_data(None)

ft.app(target=main, view=ft.AppView.FLET_APP) 