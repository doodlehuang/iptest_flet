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
            async with self.session.get('https://4.ipw.cn', timeout=5) as response:
                domestic_ip = await response.text()
                domestic_ip = domestic_ip.strip()

            async with self.session.get('http://ip-api.com/line?fields=query', timeout=5) as response:
                foreign_ip = await response.text()
                foreign_ip = foreign_ip.strip()

            async def get_ip_details(ip):
                async with self.session.get(f'http://ip-api.com/json/{ip}', timeout=5) as response:
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
        except asyncio.TimeoutError:
            return {"error": "获取IP地址时请求超时"}
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
                    async with self.session.head(url, timeout=2) as response:
                        if response.status in [204, 200]:
                            success_count += 1
                            break
                except asyncio.TimeoutError:
                    continue
                except:
                    continue

        return f"自由（{success_count}/{len(urls)}）" if success_count >= len(urls)/2 else "受限"

    async def extract_prefdomain_url(self):
        try:
            async with self.session.get('https://www.google.com', timeout=5) as response:
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
        except asyncio.TimeoutError:
            return "请求超时"
        except Exception:
            return "获取Google地区时出现错误"

    async def raw_githubusercontent_speed_test(self):
        try:
            start = datetime.datetime.now()
            async with self.session.head('https://raw.githubusercontent.com', timeout=5) as response:
                end = datetime.datetime.now()
                time_without_proxy = (end - start).total_seconds() * 1000
                return f"{time_without_proxy:.2f} 毫秒"
        except asyncio.TimeoutError:
            return "请求超时"
        except Exception as e:
            return f"GitHub连接测试出错: {e}"

    async def get_auto_login_name(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            async with self.session.get('https://login.cnki.net/TopLogin/api/loginapi/IpLoginFlush', headers=headers, timeout=5) as response:
                text = await response.text()
                result = json.loads(text[1:-1])
                if result.get('IsSuccess'):
                    return result.get('ShowName')
                return None
        except asyncio.TimeoutError:
            return "请求超时"
        except Exception:
            return None

    async def run_all_checks(self, update_callback=None):
        await self.create_session()
        tasks = {
            "ip_info": asyncio.create_task(self.get_ip_info()),
            "network_status": asyncio.create_task(self.check_network_freedom()),
            "google_region": asyncio.create_task(self.extract_prefdomain_url()),
            "github_speed": asyncio.create_task(self.raw_githubusercontent_speed_test()),
            "academic_name": asyncio.create_task(self.get_auto_login_name())
        }
        
        results = {}
        try:
            while tasks:
                # 等待任意一个任务完成
                done, pending = await asyncio.wait(
                    tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # 处理完成的任务
                for task in done:
                    # 找到对应的键
                    for key, value in list(tasks.items()):
                        if value == task:
                            try:
                                results[key] = task.result()
                                if update_callback:
                                    await update_callback(key, results[key])
                            except Exception as e:
                                results[key] = f"错误: {str(e)}"
                                if update_callback:
                                    await update_callback(key, results[key])
                            del tasks[key]
                            break
        
        finally:
            # 取消所有未完成的任务
            for task in tasks.values():
                task.cancel()
            
            await self.close_session()
        
        return results

async def main(page: ft.Page):
    page.title = "网络状态检测工具"
    page.window.height = 700
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    # 计算窗口宽度
    content_width = 400  # 内容区域最大宽度
    window_width = content_width + 40  # 加上内容区域的左右padding (20 * 2)
    page.window.width = window_width

    # 创建显示控件
    ip_info = ft.Text(size=16, selectable=True)
    network_status = ft.Text(size=16)
    google_region = ft.Text(size=16)
    github_speed = ft.Text(size=16)
    academic_info = ft.Text(size=16, visible=False)
    
    # 创建加载指示器
    ip_loading = ft.ProgressRing(width=20, height=20, visible=False)
    network_loading = ft.ProgressRing(width=20, height=20, visible=False)

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
                ip_info.value = f"IP地址：\n{ip_display}（{ip_data['region']}）"
            else:
                domestic_ip_display = ip_data['domestic_ip'] if show_full_ip else mask_ip(ip_data['domestic_ip'])
                foreign_ip_display = ip_data['foreign_ip'] if show_full_ip else mask_ip(ip_data['foreign_ip'])
                ip_info.value = f"IP地址（面向国内网站）：\n{domestic_ip_display}（{ip_data['domestic_region']}）\n" \
                               f"IP地址（面向国外网站）：\n{foreign_ip_display}（{ip_data['foreign_region']}）"
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

    async def update_single_result(key, value):
        nonlocal ip_data
        if key == "ip_info":
            ip_data = value
            update_ip_display()
        elif key == "network_status":
            network_status.value = f"网络访问状态：{value}"
        elif key == "google_region":
            google_region.value = f"Google地区：{value}"
        elif key == "github_speed":
            github_speed.value = f"GitHub连接速度：{value}"
        elif key == "academic_name":
            if value:
                academic_info.value = f"学术机构：{value}"
                academic_info.visible = True
            else:
                academic_info.visible = False
                academic_info.value = ""
        
        # 更新网络状态容器的内容
        status_controls = [
            ft.Row([
                ft.Text("网络状态", size=18, weight=ft.FontWeight.BOLD),
                network_loading
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ]
        
        if network_status.value:
            status_controls.append(network_status)
        if google_region.value:
            status_controls.append(google_region)
        if github_speed.value:
            status_controls.append(github_speed)
        if academic_info.visible:
            status_controls.append(academic_info)
            
        network_status_container.content = ft.Column(
            controls=status_controls,
            spacing=10
        )
        page.update()

    async def refresh_data(e):
        # 禁用刷新按钮并显示加载指示器
        refresh_btn.disabled = True
        ip_loading.visible = True
        network_loading.visible = True
        
        # 清空现有内容
        ip_info.value = ""
        network_status.value = ""
        google_region.value = ""
        github_speed.value = ""
        academic_info.value = ""
        academic_info.visible = False
        page.update()

        # 创建worker并运行检查
        worker = AsyncWorker()
        await worker.run_all_checks(update_callback=update_single_result)

        # 隐藏加载指示器并重新启用刷新按钮
        refresh_btn.disabled = False
        ip_loading.visible = False
        network_loading.visible = False
        page.update()

    # 创建按钮
    refresh_btn = ft.ElevatedButton(
        "刷新",
        on_click=refresh_data,
        bgcolor="#2E7D32",  # GREEN_600
        color="white",
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )

    toggle_ip_btn = ft.ElevatedButton(
        "切换IP显示模式",
        on_click=toggle_ip_display,
        bgcolor="#1565C0",  # BLUE_600
        color="white",
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )

    copy_ip_btn = ft.ElevatedButton(
        "复制IP地址",
        on_click=copy_ip_to_clipboard,
        bgcolor="#1565C0",  # BLUE_600
        color="white",
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )
    
    # 创建IP信息容器
    ip_info_container = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("IP地址信息", size=18, weight=ft.FontWeight.BOLD),
                ip_loading
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ip_info,
            ft.Row(
                [toggle_ip_btn, copy_ip_btn],
                spacing=10
            )
        ]),
        padding=15
    )
    
    # 创建网络状态容器
    network_status_container = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row([
                    ft.Text("网络状态", size=18, weight=ft.FontWeight.BOLD),
                    network_loading
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                network_status,
                google_region,
                github_speed,
                academic_info,
            ],
            spacing=10
        ),
        padding=15
    )

    # 构建界面
    content_area = ft.Container(
        content=ft.Column(
            controls=[
                # IP信息卡片
                ft.Card(
                    content=ip_info_container,
                ),
                
                # 网络状态卡片
                ft.Card(
                    content=network_status_container,
                ),
                
                # 刷新按钮
                ft.Container(
                    content=refresh_btn,
                    alignment=ft.alignment.center,
                    padding=ft.padding.only(top=20)
                )
            ],
            spacing=20,
        ),
        padding=20,
    )

    page.add(
        ft.SafeArea(
            content=ft.Column(
                controls=[
                    # 顶部标题栏
                    ft.Container(
                        content=ft.Text(
                            "网络状态检测工具",
                            size=24,
                            weight=ft.FontWeight.BOLD,
                            color="white"
                        ),
                        bgcolor="#1565C0",
                        padding=20,
                        width=float("inf"),
                        alignment=ft.alignment.center,
                    ),
                    
                    # 主要内容区域
                    ft.Container(
                        content=content_area,
                        alignment=ft.alignment.center,  # 居中显示内容区域
                    )
                ],
                spacing=0,
            )
        )
    )

    # 初始刷新
    await refresh_data(None)

ft.app(target=main, view=ft.AppView.FLET_APP) 