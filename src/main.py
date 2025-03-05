import flet as ft
import aiohttp
import asyncio
import json
from bs4 import BeautifulSoup
import datetime
import sys
import yaml
import os

def load_language(lang_code):
    """加载指定语言的翻译文本"""
    lang_file = os.path.join(os.path.dirname(__file__), 'assets', 'lang', f'{lang_code}.yaml')
    try:
        with open(lang_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading language file {lang_file}: {e}")
        return None

class LanguageManager:
    def __init__(self, default_lang='zh_CN'):
        self.current_lang = default_lang
        self.translations = {}
        self.load_translations()

    def load_translations(self):
        """加载所有支持的语言"""
        supported_langs = ['zh_CN', 'zh_TW', 'en_US']
        for lang in supported_langs:
            self.translations[lang] = load_language(lang)

    def get_text(self, key_path, lang=None):
        """获取指定路径的翻译文本"""
        lang = lang or self.current_lang
        if lang not in self.translations:
            lang = 'zh_CN'  # 默认使用简体中文
        
        translation = self.translations[lang]
        if not translation:
            return key_path  # 如果没有找到翻译文件，返回键路径
        
        # 通过路径获取翻译
        keys = key_path.split('.')
        value = translation
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return key_path
        return value

    def set_language(self, lang_code):
        """设置当前语言"""
        if lang_code in self.translations:
            self.current_lang = lang_code
            return True
        return False

class AsyncWorker:
    # 定义受限制的国家代码
    RESTRICTED_COUNTRY_CODES = ['TM', 'IR', 'KP', 'MM']

    def __init__(self, lang_manager):
        self.session = None
        self.lang_manager = lang_manager
        # 定义受限制的国家信息
        self.restricted_countries = {
            code: {
                lang: self.lang_manager.get_text(f'countries.{code}')
                for lang in ['zh_CN', 'zh_TW', 'en_US']
            }
            for code in self.RESTRICTED_COUNTRY_CODES
        }
        # 定义通用请求头
        self.browser_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-site': 'none',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-user': '?1',
            'sec-fetch-dest': 'document'
        }

    async def __aenter__(self):
        await self.create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()

    async def create_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def get_ip_info(self):
        try:
            # 首先获取国外IP信息
            async with self.session.get('http://ip-api.com/json', timeout=5) as response:
                foreign_ip_info = await response.json()
                
            # 检查是否在受限制国家
            if foreign_ip_info.get("countryCode") in self.RESTRICTED_COUNTRY_CODES:
                return {
                    "ip": foreign_ip_info["query"],
                    "region": f'{foreign_ip_info["regionName"]}, {foreign_ip_info["country"]}',
                    "restricted": True,
                    "country_code": foreign_ip_info["countryCode"]
                }
            
            # 如果不在受限制国家，继续获取国内IP
            async with self.session.get('https://4.ipw.cn', timeout=5) as response:
                domestic_ip = await response.text()
                domestic_ip = domestic_ip.strip()

            # 获取国内IP的详细信息
            async with self.session.get(f'http://ip-api.com/json/{domestic_ip}', timeout=5) as response:
                domestic_ip_info = await response.json()

            # 比较两个IP是否相同
            if domestic_ip == foreign_ip_info["query"]:
                return {"ip": domestic_ip, "region": f'{domestic_ip_info["regionName"]}, {domestic_ip_info["country"]}'}
            else:
                return {
                    "domestic_ip": domestic_ip,
                    "domestic_region": f'{domestic_ip_info["regionName"]}, {domestic_ip_info["country"]}',
                    "foreign_ip": foreign_ip_info["query"],
                    "foreign_region": f'{foreign_ip_info["regionName"]}, {foreign_ip_info["country"]}'
                }
        except asyncio.TimeoutError:
            return {"error": self.lang_manager.get_text("errors.timeout")}
        except Exception as e:
            return {"error": f"{self.lang_manager.get_text('errors.ip_error_prefix')}{e}"}

    async def check_network_freedom(self):
        urls = [
            'https://www.v2ex.com/generate_204',
            'https://www.youtube.com/generate_204',
            'https://mullvad.net/en',
            'https://www.theguardian.com/international',
            'https://bridges.torproject.org'
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

        return f"{self.lang_manager.get_text('main.network_status.status_free')}（{success_count}/{len(urls)}）" if success_count >= len(urls)/2 else self.lang_manager.get_text('main.network_status.status_restricted')

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
            return self.lang_manager.get_text("main.google.global")
        except asyncio.TimeoutError:
            return self.lang_manager.get_text("errors.google_timeout")
        except Exception:
            return self.lang_manager.get_text("errors.google_error")

    async def raw_githubusercontent_speed_test(self):
        try:
            start = datetime.datetime.now()
            async with self.session.head('https://raw.githubusercontent.com', timeout=5) as response:
                end = datetime.datetime.now()
                time_without_proxy = (end - start).total_seconds() * 1000
                return f"{time_without_proxy:.2f} {self.lang_manager.get_text('network_test.speed_unit')}"
        except asyncio.TimeoutError:
            return self.lang_manager.get_text("errors.github_timeout")
        except Exception as e:
            return self.lang_manager.get_text("errors.github_error")

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
            return self.lang_manager.get_text("errors.timeout")
        except Exception:
            return None

    async def check_netflix(self):
        """检测Netflix解锁状态"""
        try:
            # 测试两个不同的Netflix内容（LEGO Ninjago和Breaking Bad）
            urls = [
                'https://www.netflix.com/title/81280792',
                'https://www.netflix.com/title/70143836'
            ]
            
            # 更新请求头以完全匹配shell脚本
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                'accept-language': 'en-US,en;q=0.9',
                'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-site': 'none',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-user': '?1',
                'sec-fetch-dest': 'document',
                'host': 'www.netflix.com'
            }
            
            results = []
            for url in urls:
                try:
                    async with self.session.get(
                        url,
                        headers=headers,
                        timeout=10,
                        allow_redirects=True  # 允许跟随重定向
                    ) as response:
                        results.append(response.status)
                except:
                    results.append(0)

            # 分析结果
            if 0 in results:
                return self.lang_manager.get_text("main.streaming.netflix.network_error")
            
            if all(code == 404 for code in results):
                return self.lang_manager.get_text("main.streaming.netflix.originals_only")
            
            if 403 in results:
                return self.lang_manager.get_text("main.streaming.netflix.unavailable")
            
            if 200 in results:
                # 获取区域信息
                async with self.session.get(
                    'https://www.netflix.com/',
                    headers=headers,
                    timeout=10,
                    allow_redirects=True
                ) as response:
                    text = await response.text()
                    import re
                    region_match = re.search(r'"id":"([A-Z]{2})"', text)
                    region = region_match.group(1) if region_match else "UNKNOWN"
                    return self.lang_manager.get_text("main.streaming.netflix.available").format(region=region)
            
            return self.lang_manager.get_text("main.streaming.netflix.error").format(error=f"{results[0]}_{results[1]}")
            
        except Exception as e:
            return self.lang_manager.get_text("main.streaming.netflix.error").format(error=str(e))

    async def check_youtube_premium(self):
        """检测YouTube Premium解锁状态"""
        try:
            headers = self.browser_headers.copy()
            headers['cookie'] = 'YSC=FSCWhKo2Zgw; VISITOR_PRIVACY_METADATA=CgJERRIEEgAgYQ%3D%3D; PREF=f7=4000; __Secure-YEC=CgtRWTBGTFExeV9Iayjele2yBjIKCgJERRIEEgAgYQ%3D%3D; SOCS=CAISOAgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjQwNTI2LjAxX3AwGgV6aC1DTiACGgYIgMnpsgY; VISITOR_INFO1_LIVE=Di84mAIbgKY; __Secure-BUCKET=CGQ'
            
            async with self.session.get(
                'https://www.youtube.com/premium',
                headers=headers,
                timeout=10
            ) as response:
                text = await response.text()
                
                # 检查是否重定向到google.cn
                if 'www.google.cn' in text:
                    return self.lang_manager.get_text("main.streaming.youtube.unavailable_cn")
                
                # 检查是否不可用
                if 'Premium is not available in your country' in text.lower():
                    return self.lang_manager.get_text("main.streaming.youtube.unavailable")
                
                # 获取区域信息
                import re
                region_match = re.search(r'"INNERTUBE_CONTEXT_GL"\s*:\s*"([^"]+)"', text)
                region = region_match.group(1) if region_match else "UNKNOWN"
                
                # 检查是否可用
                if 'ad-free' in text.lower():
                    return self.lang_manager.get_text("main.streaming.youtube.available").format(region=region)
                
                return self.lang_manager.get_text("main.streaming.youtube.error")
                
        except Exception as e:
            return self.lang_manager.get_text("main.streaming.youtube.network_error")

    async def run_all_checks(self, update_callback=None):
        # 首先只获取IP信息
        try:
            ip_info = await self.get_ip_info()
            if update_callback:
                await update_callback("ip_info", ip_info)
            
            # 如果在受限制国家，不执行其他检查
            if ip_info.get("restricted"):
                if update_callback:
                    country_code = ip_info["country_code"]
                    country_info = self.restricted_countries[country_code]
                    await update_callback("network_status", 
                        f"{self.lang_manager.get_text('restricted_warning.prefix')}{country_info[self.lang_manager.current_lang]}{self.lang_manager.get_text('restricted_warning.suffix')}")
                    await update_callback("google_region", self.lang_manager.get_text("main.network_status.test_terminated"))
                    await update_callback("github_speed", self.lang_manager.get_text("main.network_status.test_terminated"))
                return {"ip_info": ip_info}
        except Exception as e:
            print(f"Error getting IP info: {e}")
            if update_callback:
                await update_callback("ip_info", {"error": str(e)})
            return {}

        # 如果不在受限制国家，先执行基本网络检查
        results = {"ip_info": ip_info}
        basic_tasks = {
            "network_status": lambda: self.check_network_freedom(),
            "google_region": lambda: self.extract_prefdomain_url(),
            "github_speed": lambda: self.raw_githubusercontent_speed_test(),
            "academic_name": lambda: self.get_auto_login_name()
        }
        
        # 执行基本网络检查
        active_tasks = {
            key: asyncio.create_task(factory())
            for key, factory in basic_tasks.items()
        }
        
        try:
            while active_tasks:
                done, pending = await asyncio.wait(
                    active_tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in done:
                    key = next(k for k, v in active_tasks.items() if v == task)
                    try:
                        results[key] = task.result()
                        if update_callback:
                            await update_callback(key, results[key])
                            
                            # 如果是网络状态检查完成，且网络自由，则开始流媒体检测
                            if key == "network_status" and self.lang_manager.get_text("main.network_status.status_free") in results[key]:
                                # 创建流媒体检测任务
                                streaming_tasks = {
                                    "netflix": lambda: self.check_netflix(),
                                    "youtube": lambda: self.check_youtube_premium()
                                }
                                for streaming_key, streaming_factory in streaming_tasks.items():
                                    active_tasks[streaming_key] = asyncio.create_task(streaming_factory())
                    except Exception as e:
                        results[key] = f"错误: {str(e)}"
                        if update_callback:
                            await update_callback(key, results[key])
                    
                    del active_tasks[key]
        
        except Exception as e:
            print(f"Error in run_all_checks: {e}")
            for task in active_tasks.values():
                task.cancel()
            
        return results

async def main(page: ft.Page):
    page.title = ""
    page.window.height = 800
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    # 计算窗口宽度
    content_width = 400  # 内容区域最大宽度
    window_width = content_width + 40  # 加上内容区域的左右padding (20 * 2)
    page.window.width = window_width

    # 初始化语言管理器
    lang_manager = LanguageManager()
    
    # 创建加载指示器
    ip_loading = ft.ProgressRing(width=20, height=20, visible=False)
    network_loading = ft.ProgressRing(width=20, height=20, visible=False)
    
    # 创建流媒体测试的加载指示器
    netflix_loading = ft.ProgressRing(width=16, height=16, visible=False)
    youtube_loading = ft.ProgressRing(width=16, height=16, visible=False)
    
    # 创建状态显示控件
    ip_info = ft.Text("", selectable=True)
    network_status = ft.Text("")
    google_region = ft.Text("")
    github_speed = ft.Text("")
    academic_info = ft.Text("", visible=False)
    
    # 创建流媒体测试状态显示控件
    netflix_status = ft.Text("", size=14)
    youtube_status = ft.Text("", size=14)
    
    # 创建流媒体测试容器
    streaming_container = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    lang_manager.get_text("main.streaming.title"),
                    size=18,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Column([
                    # Netflix检测行
                    ft.Row([
                        ft.Container(
                            content=ft.Text("Netflix", size=14),
                            width=120
                        ),
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    netflix_status,
                                    netflix_loading
                                ],
                                spacing=10
                            ),
                            expand=True
                        )
                    ], alignment=ft.MainAxisAlignment.START),
                    # YouTube Premium检测行
                    ft.Row([
                        ft.Container(
                            content=ft.Text("YouTube Premium", size=14),
                            width=120
                        ),
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    youtube_status,
                                    youtube_loading
                                ],
                                spacing=10
                            ),
                            expand=True
                        )
                    ], alignment=ft.MainAxisAlignment.START)
                ], spacing=10)
            ],
            spacing=10
        ),
        padding=15,
        visible=False  # 初始状态为隐藏
    )

    # 用于存储IP信息的变量
    ip_data = {}
    show_full_ip = False

    # 创建按钮（先声明，后面再设置on_click）
    refresh_btn = ft.ElevatedButton(
        lang_manager.get_text("buttons.refresh"),
        bgcolor="#2E7D32",  # GREEN_600
        color="white",
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8)
        )
    )

    toggle_ip_btn = ft.ElevatedButton(
        lang_manager.get_text("main.ip_info.toggle"),
        bgcolor="#1565C0",  # BLUE_600
        color="white",
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8)
        ),
        visible=False  # 初始不可见
    )

    copy_ip_btn = ft.ElevatedButton(
        lang_manager.get_text("main.ip_info.copy"),
        bgcolor="#1565C0",  # BLUE_600
        color="white",
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8)
        ),
        visible=False  # 初始不可见
    )

    # 创建复制成功提示横幅
    copy_banner = ft.Banner(
        bgcolor=ft.Colors.GREEN_100,
        leading=ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN, size=40),
        content=ft.Text(
            lang_manager.get_text("copy.success"),
            color=ft.Colors.GREEN
        ),
        actions=[
            ft.TextButton(
                lang_manager.get_text("buttons.ok"),
                on_click=lambda e: (setattr(copy_banner, "open", False), page.update())
            )
        ]
    )
    page.banner = copy_banner

    def mask_ip(ip):
        parts = ip.split('.')
        return '.'.join(parts[:2] + ['*', '*'])

    def format_ip_info(ip_info, region):
        ip_display = ip_info if show_full_ip else mask_ip(ip_info)
        return f"{ip_display}（{region}）"

    def update_ip_display():
        if "error" in ip_data:
            ip_info.value = ip_data["error"]
            toggle_ip_btn.visible = False
            copy_ip_btn.visible = False
            return

        if "ip" in ip_data:
            ip_info.value = f"{lang_manager.get_text('main.ip_info.single')}\n{format_ip_info(ip_data['ip'], ip_data['region'])}"
        else:
            domestic = format_ip_info(ip_data['domestic_ip'], ip_data['domestic_region'])
            foreign = format_ip_info(ip_data['foreign_ip'], ip_data['foreign_region'])
            ip_info.value = f"{lang_manager.get_text('main.ip_info.domestic')}\n{domestic}\n" \
                           f"{lang_manager.get_text('main.ip_info.foreign')}\n{foreign}"
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
            page.set_clipboard(f"{lang_manager.get_text('main.ip_info.domestic')}{ip_data['domestic_ip']}, {lang_manager.get_text('main.ip_info.foreign')}{ip_data['foreign_ip']}")
        copy_banner.open = True
        page.update()

    # 设置按钮的on_click事件
    toggle_ip_btn.on_click = toggle_ip_display
    copy_ip_btn.on_click = copy_ip_to_clipboard

    def check_all_network_items_loaded():
        required_items = [
            network_status.value,
            google_region.value,
            github_speed.value
        ]
        return all(required_items) and (academic_info.value or not academic_info.visible)

    def update_network_status_ui():
        status_controls = [
            ft.Row([
                ft.Text(lang_manager.get_text("main.network_status.title"), size=18, weight=ft.FontWeight.BOLD),
                network_loading
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ]
        
        for control in [network_status, google_region, github_speed]:
            if control.value:
                status_controls.append(control)
        
        if academic_info.visible:
            status_controls.append(academic_info)
            
        network_status_container.content = ft.Column(
            controls=status_controls,
            spacing=10
        )

    async def update_single_result(key, value):
        nonlocal ip_data
        if key == "ip_info":
            ip_data = value
            update_ip_display()
            ip_loading.visible = False
            toggle_ip_btn.visible = "error" not in ip_data
            copy_ip_btn.visible = "error" not in ip_data
            page.update()
        elif key == "network_status":
            network_status.value = f"{lang_manager.get_text('main.network_status.status_prefix')}{value}"
            is_network_free = lang_manager.get_text("main.network_status.status_free") in value
            
            # 只在首次设置网络状态为自由时显示流媒体测试卡片和启动检测
            if is_network_free and not streaming_container.visible:
                streaming_container.visible = True
                netflix_status.value = ""
                youtube_status.value = ""
                netflix_status.visible = True
                youtube_status.visible = True
                netflix_loading.visible = True
                youtube_loading.visible = True
            elif not is_network_free:
                streaming_container.visible = False
                netflix_loading.visible = False
                youtube_loading.visible = False
            page.update()
        elif key == "google_region":
            google_region.value = f"{lang_manager.get_text('main.network_status.google_region_prefix')}{value}"
            page.update()
        elif key == "github_speed":
            github_speed.value = f"{lang_manager.get_text('main.network_status.github_speed_prefix')}{value}"
            page.update()
        elif key == "academic_name":
            academic_info.visible = bool(value)
            academic_info.value = f"{lang_manager.get_text('main.network_status.academic_prefix')}{value}" if value else ""
            page.update()
        elif key == "netflix":
            netflix_loading.visible = False
            netflix_status.value = value
            netflix_status.visible = True
            page.update()
        elif key == "youtube":
            youtube_loading.visible = False
            youtube_status.value = value
            youtube_status.visible = True
            page.update()

        # 只在所有基本网络检查项目完成时显示一次完成消息
        if check_all_network_items_loaded() and network_loading.visible:
            network_loading.visible = False
            page.update()
        
        # 更新网络状态UI
        update_network_status_ui()
        page.update()

    async def refresh_data(e):
        # 禁用刷新按钮并显示加载指示器
        refresh_btn.disabled = True
        ip_loading.visible = True
        network_loading.visible = True
        streaming_container.visible = False
        
        # 隐藏操作按钮
        toggle_ip_btn.visible = False
        copy_ip_btn.visible = False
        
        # 清空现有内容
        ip_info.value = ""
        network_status.value = ""
        google_region.value = ""
        github_speed.value = ""
        academic_info.value = ""
        academic_info.visible = False
        
        # 重置流媒体测试状态
        netflix_status.value = ""
        youtube_status.value = ""
        netflix_loading.visible = False
        youtube_loading.visible = False
        page.update()

        # 创建worker并运行检查
        async with AsyncWorker(lang_manager) as worker:
            await worker.run_all_checks(update_callback=update_single_result)

        # 隐藏加载指示器并重新启用刷新按钮
        refresh_btn.disabled = False
        ip_loading.visible = False
        network_loading.visible = False
        page.update()

    # 设置刷新按钮的on_click事件
    refresh_btn.on_click = refresh_data

    # 创建IP信息容器
    ip_info_container = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text(
                    lang_manager.get_text("main.ip_info.title"),
                    size=18,
                    weight=ft.FontWeight.BOLD
                ),
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
                    ft.Text(
                        lang_manager.get_text("main.network_status.title"),
                        size=18,
                        weight=ft.FontWeight.BOLD
                    ),
                    network_loading
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                network_status,
                google_region,
                github_speed,
                academic_info
            ],
            spacing=10
        ),
        padding=15
    )

    # 创建主要内容区域
    content_area = ft.Container(
        content=ft.Column(
            controls=[
                # IP信息卡片
                ft.Card(
                    content=ip_info_container
                ),
                
                # 网络状态卡片
                ft.Card(
                    content=network_status_container
                ),
                
                # 流媒体测试卡片
                ft.Card(
                    content=streaming_container
                ),
                
                # 刷新按钮
                ft.Container(
                    content=refresh_btn,
                    alignment=ft.alignment.center,
                    padding=ft.padding.only(top=20)
                )
            ],
            spacing=20
        ),
        padding=20
    )

    # 语言切换函数
    def change_language(new_lang):
        if lang_manager.set_language(new_lang):
            # 更新所有文本
            page.title = lang_manager.get_text("app.title")
            copy_banner.content.value = lang_manager.get_text("copy.success")
            copy_banner.actions[0].text = lang_manager.get_text("buttons.ok")
            
            # 更新警告页面的文本
            warning_screen.controls[0].content.value = lang_manager.get_text("app.title")
            warning_content = warning_screen.controls[1].content.controls
            warning_content[1].value = lang_manager.get_text("warning.title")
            warning_content[2].value = (
                lang_manager.get_text("warning.message") + "\n\n" +
                lang_manager.get_text("warning.restricted_countries_prefix") + "\n" +
                "\n".join([f"• {lang_manager.get_text(f'countries.{code}')}" for code in AsyncWorker.RESTRICTED_COUNTRY_CODES]) + "\n\n" +
                lang_manager.get_text("warning.agreement")
            )
            warning_content[3].content.content.value = lang_manager.get_text("warning.disclaimer")
            warning_content[4].controls[0].value = lang_manager.get_text("settings.language")
            warning_content[5].controls[0].text = lang_manager.get_text("warning.continue")
            warning_content[5].controls[1].text = lang_manager.get_text("warning.cancel")
            
            # 更新按钮文本
            refresh_btn.text = lang_manager.get_text("buttons.refresh")
            toggle_ip_btn.text = lang_manager.get_text("main.ip_info.toggle")
            copy_ip_btn.text = lang_manager.get_text("main.ip_info.copy")

            # 更新主界面的标题
            if ip_info_container:
                ip_info_container.content.controls[0].controls[0].value = lang_manager.get_text("main.ip_info.title")
            if network_status_container:
                network_status_container.content.controls[0].controls[0].value = lang_manager.get_text("main.network_status.title")
            if streaming_container:
                streaming_container.content.controls[0].value = lang_manager.get_text("main.streaming.title")
            
            # 更新页面
            page.update()

    # 创建警告界面
    async def handle_warning_action(e):
        if e.control.data:  # 如果用户点击"继续"
            page.clean()
            # 更新页面标题
            page.title = lang_manager.get_text("app.title")
            page.add(
                ft.SafeArea(
                    ft.Column(
                        controls=[
                            copy_banner,
                            ft.Container(
                                content=ft.Text(
                                    lang_manager.get_text("app.title"),
                                    size=24,
                                    weight=ft.FontWeight.BOLD,
                                    color="white"
                                ),
                                bgcolor="#1565C0",
                                padding=15,
                                width=float("inf"),
                                alignment=ft.alignment.center
                            ),
                            ft.Container(
                                content=ft.Column(
                                    controls=[content_area],
                                    scroll=ft.ScrollMode.AUTO,
                                    expand=True
                                ),
                                alignment=ft.alignment.top_center,
                                expand=True
                            )
                        ],
                        spacing=0,
                        expand=True
                    ),
                    expand=True
                )
            )

            # 更新主界面的标题文本
            ip_info_container.content.controls[0].controls[0].value = lang_manager.get_text("main.ip_info.title")
            network_status_container.content.controls[0].controls[0].value = lang_manager.get_text("main.network_status.title")
            page.update()

            await refresh_data(None)
        else:  # 如果用户点击"取消"
            page.window.close()
        page.update()

    warning_screen = ft.Column(
        controls=[
            ft.Container(
                content=ft.Text(
                    lang_manager.get_text("app.title"),
                    size=24,
                    weight=ft.FontWeight.BOLD,
                    color="white"
                ),
                bgcolor="#1565C0",
                padding=15,
                width=float("inf"),
                alignment=ft.alignment.center
            ),
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            name=ft.Icons.WARNING_AMBER_ROUNDED,
                            color=ft.Colors.AMBER,
                            size=64
                        ),
                        ft.Text(
                            lang_manager.get_text("warning.title"),
                            size=24,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            lang_manager.get_text("warning.message") + "\n\n" +
                            lang_manager.get_text("warning.restricted_countries_prefix") + "\n" +
                            "\n".join([f"• {lang_manager.get_text(f'countries.{code}')}" for code in AsyncWorker.RESTRICTED_COUNTRY_CODES]) + "\n\n" +
                            lang_manager.get_text("warning.agreement"),
                            text_align=ft.TextAlign.CENTER,
                            size=16
                        ),
                        ft.Container(
                            content=ft.Container(
                                content=ft.Text(
                                    lang_manager.get_text("warning.disclaimer"),
                                    text_align=ft.TextAlign.CENTER,
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.GREY_700,
                                ),
                                padding=15,
                                bgcolor=ft.Colors.ORANGE_50,
                                border=ft.border.all(1, ft.Colors.ORANGE_200),
                                border_radius=8,
                            ),
                            padding=ft.padding.symmetric(horizontal=20),
                            margin=ft.margin.only(bottom=10, top=5)
                        ),
                        ft.Row(
                            controls=[
                                ft.Text(
                                    lang_manager.get_text("settings.language"),
                                    size=16
                                ),
                                ft.Dropdown(
                                    value=lang_manager.current_lang,
                                    options=[
                                        ft.dropdown.Option("zh_CN", "简体中文"),
                                        ft.dropdown.Option("zh_TW", "繁體中文"),
                                        ft.dropdown.Option("en_US", "English")
                                    ],
                                    on_change=lambda e: change_language(e.data),
                                    width=150
                                )
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=20
                        ),
                        ft.Row(
                            controls=[
                                ft.ElevatedButton(
                                    text=lang_manager.get_text("warning.continue"),
                                    on_click=handle_warning_action,
                                    data=True
                                ),
                                ft.OutlinedButton(
                                    text=lang_manager.get_text("warning.cancel"),
                                    on_click=handle_warning_action,
                                    data=False
                                )
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=20
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=15,
                    scroll=ft.ScrollMode.ALWAYS,
                    expand=True
                ),
                padding=20,
                expand=True
            )
        ],
        spacing=0,
        expand=True
    )

    # 添加警告界面
    page.add(
        ft.SafeArea(
            warning_screen,
            expand=True
        )
    )
    page.update()

ft.app(target=main, view=ft.AppView.FLET_APP) 