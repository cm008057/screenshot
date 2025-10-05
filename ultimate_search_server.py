from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import pandas as pd
import os
import time
import random
import json
from datetime import datetime
# from ocr_analyzer import NegativeWordAnalyzer  # OCR機能は一時的に無効化

app = Flask(__name__)
CORS(app)

def setup_driver(headless=True):
    """最適化されたブラウザ設定 - ボット検出回避強化版"""
    options = Options()

    if headless:
        options.add_argument('--headless=new')  # 新しいheadlessモード
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        print("🔇 ヘッドレスモードで実行中（画面に表示されません）")
    else:
        print("🖥️ ブラウザ表示モードで実行中")

    # ウィンドウサイズを一般的な解像度に
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')

    # 自動化検出の無効化
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)

    # リアルなUser-Agent（定期的に更新推奨）
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    # 自動化フラグの削除
    options.add_argument('--disable-blink-features=AutomationControlled')

    # 言語とロケール設定
    options.add_argument('--lang=ja-JP')
    options.add_argument('--accept-lang=ja-JP,ja;q=0.9')

    # その他のボット対策
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-notifications')

    # プライバシー設定（通常ブラウザに近づける）
    prefs = {
        'profile.default_content_setting_values.notifications': 2,
        'credentials_enable_service': False,
        'profile.password_manager_enabled': False,
        'profile.default_content_settings.popups': 0,
        'download.prompt_for_download': False,
        'plugins.always_open_pdf_externally': True
    }
    options.add_experimental_option('prefs', prefs)

    # バックグラウンド実行のための追加設定
    if headless:
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')

    driver = webdriver.Chrome(options=options)

    # JavaScript実行でさらにボット検出を回避
    stealth_js = """
        // navigator.webdriverを完全に削除
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

        // Chrome検出を回避
        window.navigator.chrome = {
            runtime: {},
        };

        // Permissions APIの偽装
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );

        // Plugin配列の偽装
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Languages配列の偽装
        Object.defineProperty(navigator, 'languages', {
            get: () => ['ja-JP', 'ja', 'en-US', 'en'],
        });
    """

    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': stealth_js})

    return driver

def prepare_company_variations(company_name, selected_patterns=None):
    """株式会社パターン準備（選択されたもののみ）"""
    all_variations = []
    
    if '株式会社' in company_name:
        all_variations.append({'name': company_name, 'type': 'with_corp'})
        all_variations.append({'name': company_name.replace('株式会社', '').strip(), 'type': 'without_corp'})
    else:
        all_variations.append({'name': company_name, 'type': 'original'})
        all_variations.append({'name': f'株式会社{company_name}', 'type': 'prefix_corp'})
        if not company_name.endswith('株式会社'):
            all_variations.append({'name': f'{company_name}株式会社', 'type': 'suffix_corp'})
    
    # 選択されたパターンのみを返す
    if selected_patterns:
        return [v for v in all_variations if v['type'] in selected_patterns]
    
    return all_variations

def get_search_box(driver, engine_name):
    """検索ボックス取得"""
    if engine_name == 'google':
        try:
            return driver.find_element(By.NAME, "q")
        except:
            try:
                return driver.find_element(By.CSS_SELECTOR, 'textarea[name="q"]')
            except:
                return driver.find_element(By.CSS_SELECTOR, 'input[name="q"]')
    elif engine_name == 'yahoo':
        return driver.find_element(By.NAME, "p")
    elif engine_name == 'bing':
        try:
            return driver.find_element(By.ID, "sb_form_q")
        except:
            return driver.find_element(By.NAME, "q")

def human_like_typing(element, text):
    """人間らしいタイピング動作"""
    for char in text:
        element.send_keys(char)
        # タイピング速度をランダムに変える
        delay = random.uniform(0.05, 0.25)
        # たまに長めの間隔（考えている風）
        if random.random() < 0.1:
            delay = random.uniform(0.3, 0.7)
        time.sleep(delay)

def human_like_mouse_move(driver, element):
    """人間らしいマウス移動（スクロールとホバー）"""
    try:
        # 要素までスクロール
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(random.uniform(0.3, 0.7))

        # マウスホバー風の動き
        from selenium.webdriver.common.action_chains import ActionChains
        actions = ActionChains(driver)
        actions.move_to_element(element).perform()
        time.sleep(random.uniform(0.2, 0.5))
    except:
        pass

def random_page_interaction(driver):
    """ランダムなページ操作（人間らしさ向上）"""
    actions = [
        lambda: driver.execute_script("window.scrollBy(0, {});".format(random.randint(50, 150))),
        lambda: driver.execute_script("window.scrollBy(0, {});".format(random.randint(-100, -50))),
        lambda: time.sleep(random.uniform(0.5, 1.5))
    ]

    # 20%の確率でランダム操作
    if random.random() < 0.2:
        random.choice(actions)()

def detect_google_maps(driver):
    """Googleマップ表示を検出"""
    try:
        # 右側のマップパネルを検索
        map_selectors = [
            '[data-attrid="kc:/location/location:address"]',
            '[data-attrid="kc:/business/business:hours"]',
            '.UaQhfb',  # 地図コンテナ
            '[data-ved][data-async-context="action:map"]',
            '.L6Djkc'  # マップパネル
        ]
        
        for selector in map_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"Googleマップ検出: {selector}")
                return True
        return False
    except Exception as e:
        print(f"マップ検出エラー: {e}")
        return False

def process_search_with_options(driver, engine_name, variation, base_path, options):
    """オプション付き検索処理"""
    results = {
        'variation': variation['name'],
        'type': variation['type'],
        'suggest': None,
        'related_words': None,
        'google_maps': None,
        'reputation_suggest': None,
        'reputation_related': None,
        'review_suggest': None,
        'review_related': None
    }
    
    try:
        # 基本URL設定
        if engine_name == 'google':
            url = 'https://www.google.com/webhp?hl=ja'
        elif engine_name == 'yahoo':
            url = 'https://www.yahoo.co.jp/'
        elif engine_name == 'bing':
            url = 'https://www.bing.com/?cc=jp'
            
        # Bingの場合は追加の待機時間
        extra_delay = 2 if engine_name == 'bing' else 0
        
        # 1. 基本サジェスト取得
        if options.get('basic_suggest', True):
            driver.get(url)
            time.sleep(2 + extra_delay)
            
            search_box = get_search_box(driver, engine_name)

            # 人間らしいマウス移動
            human_like_mouse_move(driver, search_box)

            search_box.click()
            search_box.clear()

            # 人間らしいタイピング
            human_like_typing(search_box, variation['name'])

            # ランダムなページ操作
            random_page_interaction(driver)

            time.sleep(random.uniform(2, 4))
            
            suggest_path = os.path.join(base_path, f'{engine_name}_suggest_{variation["type"]}.png')
            driver.save_screenshot(suggest_path)
            results['suggest'] = suggest_path
            
            # 検索実行
            search_box.send_keys(Keys.RETURN)
            time.sleep(random.uniform(4, 6))
            
            # Googleマップ検出
            if engine_name == 'google' and options.get('google_maps', False):
                if detect_google_maps(driver):
                    maps_path = os.path.join(base_path, f'{engine_name}_maps_{variation["type"]}.png')
                    driver.save_screenshot(maps_path)
                    results['google_maps'] = maps_path
                    print(f"Googleマップスクリーンショット保存: {maps_path}")
            
            # 関連ワード取得
            if options.get('related_words', True):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                related_path = os.path.join(base_path, f'{engine_name}_related_{variation["type"]}.png')
                driver.save_screenshot(related_path)
                results['related_words'] = related_path
        
        # 2. 評判検索
        if options.get('reputation_search', False):
            driver.get(url)
            time.sleep(2 + extra_delay)
            
            search_box = get_search_box(driver, engine_name)
            human_like_mouse_move(driver, search_box)
            search_box.click()
            search_box.clear()

            reputation_query = f'{variation["name"]} 評判'
            human_like_typing(search_box, reputation_query)
            random_page_interaction(driver)
            
            time.sleep(2)
            
            rep_suggest_path = os.path.join(base_path, f'{engine_name}_reputation_suggest_{variation["type"]}.png')
            driver.save_screenshot(rep_suggest_path)
            results['reputation_suggest'] = rep_suggest_path
            
            search_box.send_keys(Keys.RETURN)
            time.sleep(3)
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            rep_related_path = os.path.join(base_path, f'{engine_name}_reputation_related_{variation["type"]}.png')
            driver.save_screenshot(rep_related_path)
            results['reputation_related'] = rep_related_path
        
        # 3. 口コミ検索
        if options.get('review_search', False):
            driver.get(url)
            time.sleep(2 + extra_delay)
            
            search_box = get_search_box(driver, engine_name)
            human_like_mouse_move(driver, search_box)
            search_box.click()
            search_box.clear()

            review_query = f'{variation["name"]} 口コミ'
            human_like_typing(search_box, review_query)
            random_page_interaction(driver)
            
            time.sleep(2)
            
            review_suggest_path = os.path.join(base_path, f'{engine_name}_review_suggest_{variation["type"]}.png')
            driver.save_screenshot(review_suggest_path)
            results['review_suggest'] = review_suggest_path
            
            search_box.send_keys(Keys.RETURN)
            time.sleep(3)
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            review_related_path = os.path.join(base_path, f'{engine_name}_review_related_{variation["type"]}.png')
            driver.save_screenshot(review_related_path)
            results['review_related'] = review_related_path
        
    except Exception as e:
        print(f"{engine_name} 処理エラー ({variation['name']}): {e}")
        results['error'] = str(e)
    
    return results

@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    """Excelファイルアップロード処理"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'ファイルが選択されていません'})
        
        # ファイル保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"uploaded_companies_{timestamp}.xlsx"
        filepath = os.path.join(os.path.dirname(__file__), filename)
        file.save(filepath)
        
        # Excel読み込み
        df = pd.read_excel(filepath)
        
        # 最初の列を会社名として使用
        company_column = df.columns[0]
        companies = df[company_column].dropna().astype(str).tolist()
        
        # 重複削除
        companies = list(dict.fromkeys(companies))
        
        return jsonify({
            'success': True,
            'companies': companies,
            'count': len(companies),
            'column_name': company_column
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Excelファイル読み込みエラー: {str(e)}'
        })

@app.route('/get_company_patterns', methods=['POST'])
def get_company_patterns():
    """会社名パターン生成"""
    try:
        data = request.json
        company_name = data.get('company_name', '')
        
        if not company_name:
            return jsonify({'success': False, 'error': '会社名が入力されていません'})
        
        patterns = prepare_company_variations(company_name)
        
        return jsonify({
            'success': True,
            'company_name': company_name,
            'patterns': patterns
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/ultimate_search', methods=['POST'])
def ultimate_search():
    """最終版検索システム"""
    try:
        data = request.json
        companies = data.get('companies', [])
        selected_patterns = data.get('selected_patterns', {})
        search_options = data.get('options', {})
        
        if not companies:
            return jsonify({'success': False, 'error': '会社が選択されていません'})
        
        # 保存先フォルダ作成
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        folder_name = f"ultimate_search_batch_{timestamp}"
        folder_path = os.path.join(os.path.dirname(__file__), folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # WebDriver初期化（ヘッドレスモード設定を取得）
        headless_mode = search_options.get('headless_mode', True)
        driver = setup_driver(headless=headless_mode)
        all_results = {}
        
        try:
            total_companies = len(companies)
            processed_companies = 0
            
            for company_name in companies:
                print(f"\n=== 処理中: {company_name} ({processed_companies+1}/{total_companies}) ===")
                
                # 会社別フォルダ作成
                safe_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                company_folder = os.path.join(folder_path, safe_name)
                os.makedirs(company_folder, exist_ok=True)
                
                # パターン準備
                company_patterns = selected_patterns.get(company_name, [])
                if not company_patterns:
                    # デフォルトパターン
                    variations = prepare_company_variations(company_name)
                else:
                    variations = prepare_company_variations(company_name, company_patterns)
                
                company_results = {}
                
                # 各検索エンジンで処理
                engines = []
                if search_options.get('enable_google', True):
                    engines.append('google')
                if search_options.get('enable_yahoo', True):
                    engines.append('yahoo')
                if search_options.get('enable_bing', True):
                    engines.append('bing')
                
                for engine in engines:
                    print(f"  {engine.upper()} 処理中...")
                    
                    engine_folder = os.path.join(company_folder, engine)
                    os.makedirs(engine_folder, exist_ok=True)
                    
                    engine_results = []
                    
                    for variation in variations:
                        result = process_search_with_options(
                            driver, engine, variation, engine_folder, search_options
                        )
                        engine_results.append(result)
                        
                        # 少し待機
                        time.sleep(random.uniform(3, 6))
                    
                    company_results[engine] = engine_results
                    
                    # エンジン間での待機
                    time.sleep(random.uniform(8, 12))
                
                all_results[company_name] = company_results
                processed_companies += 1
                
                # 会社間での待機
                if processed_companies < total_companies:
                    time.sleep(random.uniform(3, 5))
        
        finally:
            driver.quit()
        
        # OCR分析（有効な場合）
        ocr_results = {}
        if search_options.get('enable_ocr', False):
            print("\n=== OCR分析開始 ===")
            print("⚠️ OCR機能は現在無効化されています")
            """
            try:
                analyzer = NegativeWordAnalyzer()
                
                for company_name in companies:
                    safe_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    company_folder = os.path.join(folder_path, safe_name)
                    
                    if os.path.exists(company_folder):
                        company_ocr = analyzer.analyze_folder(company_folder)
                        
                        # JSONレポート保存
                        json_filename = f"ocr_report_{safe_name}_{timestamp}.json"
                        json_path = os.path.join(company_folder, json_filename)
                        analyzer.save_report(company_ocr, json_path)
                        
                        # HTMLレポート保存
                        html_filename = f"ocr_report_{safe_name}_{timestamp}.html"
                        html_path = os.path.join(company_folder, html_filename)
                        analyzer.save_html_report(company_ocr, html_path)
                        
                        ocr_results[company_name] = {
                            'json_path': json_path,
                            'html_path': html_path,
                            'summary': company_ocr['summary'],
                            'risk_assessment': company_ocr['risk_assessment']
                        }
            
            except Exception as e:
                print(f"OCR分析エラー: {e}")
                ocr_results = {'error': str(e)}
            """
        
        # 全体サマリー作成
        summary = {
            'total_companies': len(companies),
            'processed_companies': processed_companies,
            'total_screenshots': 0,
            'enabled_options': search_options
        }
        
        # スクリーンショット数カウント
        for company_results in all_results.values():
            for engine_results in company_results.values():
                for result in engine_results:
                    for key, value in result.items():
                        if key.endswith(('suggest', 'related', 'maps')) and value:
                            summary['total_screenshots'] += 1
        
        return jsonify({
            'success': True,
            'folder': folder_path,
            'companies': companies,
            'results': all_results,
            'ocr_results': ocr_results,
            'summary': summary,
            'message': f'{processed_companies}社の処理が完了しました'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/')
def index():
    """トップページ - HTMLを表示"""
    return send_from_directory('.', 'ultimate_search.html')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    print("=" * 70)
    print("🚀 ULTIMATE SEARCH SYSTEM - 完全版")
    print("=" * 70)
    print("http://localhost:8006 で起動中")
    print("\n🔥 全機能搭載:")
    print("📊 Excel一括読み込み")
    print("⚙️  株式会社パターン手動選択")
    print("🗺️  Googleマップ自動検出")
    print("💬 評判・口コミ検索")
    print("🤖 OCRネガティブワード分析")
    print("🎛️  全機能ON/OFF切り替え")
    print("=" * 70)
    app.run(host='0.0.0.0', port=8006, debug=True)