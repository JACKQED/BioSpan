import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# 1. 精准化 PubMed 检索词（聚焦衰老生物学、哺乳动物与人类临床、排除农业/植物/兽医）
SEARCH_QUERY = (
    '("Longevity"[Mesh] OR "Aging"[Mesh] OR "Geroscience"[tiab] OR "Senolytics"[tiab] OR '
    '"Rapamycin"[tiab] OR "Metformin"[tiab] OR "NAD+"[tiab] OR "cellular senescence"[tiab]) AND '
    '("Clinical Trial"[Publication Type] OR "Randomized Controlled Trial"[Publication Type] OR "Review"[Publication Type] OR "humans"[MeSH Terms]) '
    'NOT ("Plants"[Mesh] OR "Plant"[tiab] OR "Veterinary"[tiab] OR "Agriculture"[tiab])'
)


def get_full_text(element):
    """递归提取 XML 元素下的所有文本，包含内联 HTML 标签"""
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def detect_topic_tag(text):
    """根据标题/摘要内容智能匹配分类标签与 Tailwind 颜色样式"""
    t = text.lower()
    if any(k in t for k in ["rapamycin", "mtor", "autophagy", "everolimus"]):
        return "mTOR / 雷帕霉素", "bg-purple-500/10 text-purple-400 border-purple-500/20"
    if any(k in t for k in ["senolytic", "senescence", "dasatinib", "quercetin", "fisetin", "sasp"]):
        return "Senolytics / 清除衰老细胞", "bg-rose-500/10 text-rose-400 border-rose-500/20"
    if any(k in t for k in ["nad+", "nmn", "nr", "sirtuin", "mitochondria", "sirt1"]):
        return "NAD+ / 线粒体代谢", "bg-blue-500/10 text-blue-400 border-blue-500/20"
    if any(k in t for k in ["gut", "microbiome", "microbiota", "short-chain fatty"]):
        return "肠道菌群 / 免疫衰老", "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
    if any(k in t for k in ["metformin", "ampk", "glucose", "acarbose", "sglt2"]):
        return "AMPK / 代谢干预", "bg-teal-500/10 text-teal-400 border-teal-500/20"
    return "衰老生物学前沿", "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"


def safe_request(url, headers=None, data=None, timeout=15, max_retries=3):
    """封装带重试与 User-Agent 的安全网络请求"""
    default_headers = {"User-Agent": "BioSpan-Research-Bot/1.0 (https://jackqed.github.io/BioSpan/)"}
    if headers:
        default_headers.update(headers)
    
    req = urllib.request.Request(url, data=data, headers=default_headers)
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 * (attempt + 1))
            else:
                print(f"HTTP 请求错误 ({e.code}): {url}")
                break
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"网络请求失败 [{attempt+1}/{max_retries}]: {e}")
            time.sleep(1.5)
    return None


# ==================== Step 1: 从 PubMed 获取前沿论文 ====================
encoded_query = urllib.parse.quote(SEARCH_QUERY)
esearch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={encoded_query}&retmax=6&sort=pub_date"

search_res = safe_request(esearch_url)
id_list = []
if search_res:
    try:
        tree = ET.fromstring(search_res)
        id_list = [id_elem.text for id_elem in tree.findall(".//IdList/Id") if id_elem.text]
    except Exception as e:
        print(f"解析 PubMed ID 列表失败: {e}")

cards_html = ""
email_articles_html = ""
valid_articles_count = 0

if id_list:
    efetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={','.join(id_list)}&retmode=xml"
    fetch_res = safe_request(efetch_url, timeout=20)
    
    if fetch_res:
        try:
            fetch_tree = ET.fromstring(fetch_res)
            articles = fetch_tree.findall(".//PubmedArticle")

            for article in articles:
                if valid_articles_count >= 4:
                    break

                pmid = article.findtext(".//PMID", default="")
                if not pmid:
                    continue

                # 提取标题
                title_elem = article.find(".//ArticleTitle")
                title_raw = get_full_text(title_elem) if title_elem is not None else "最新衰老机制与干预研究"
                title = html.escape(title_raw.rstrip("."))

                # 提取完整结构化摘要
                abstract_nodes = article.findall(".//AbstractText")
                if abstract_nodes:
                    full_abstract = " ".join([get_full_text(node) for node in abstract_nodes])
                    abstract_clean = re.sub(r"\s+", " ", full_abstract).strip()
                    abstract = html.escape(abstract_clean[:220] + "..." if len(abstract_clean) > 220 else abstract_clean)
                else:
                    abstract = "该同行评审论文详细探讨了衰老分子靶点、代谢调控或延寿化合物的最新作用机制与临床验证。"

                # 提取期刊名称
                journal_elem = article.find(".//Journal/Title")
                journal_raw = get_full_text(journal_elem) if journal_elem is not None else "Peer-Reviewed Journal"
                journal = html.escape(journal_raw)

                # 分类标签
                tag_name, tag_style = detect_topic_tag(title_raw + " " + abstract)

                # 生成前端网页卡片
                cards_html += f"""
            <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl hover:border-emerald-500/40 transition flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between mb-3">
                        <span class="text-xs font-semibold px-2.5 py-1 rounded border {tag_style}">{tag_name}</span>
                        <span class="text-xs text-slate-500">PMID: {pmid}</span>
                    </div>
                    <h3 class="text-base font-bold text-white mb-2 line-clamp-2" title="{title}">{title}</h3>
                    <p class="text-slate-400 text-xs leading-relaxed mb-4">{abstract}</p>
                </div>
                <div class="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs">
                    <span class="text-slate-400 truncate max-w-[200px]" title="{journal}"><i class="fa-solid fa-book-journal-whills mr-1 text-emerald-400"></i> {journal}</span>
                    <a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/" target="_blank" rel="noopener noreferrer" class="text-emerald-400 hover:text-emerald-300 font-medium flex items-center">
                        查看原文 <i class="fa-solid fa-arrow-up-right-from-square ml-1 text-[10px]"></i>
                    </a>
                </div>
            </div>"""

                # 生成邮件卡片
                email_articles_html += f"""
            <div style="margin-bottom: 20px; padding: 18px; border: 1px solid #e2e8f0; border-radius: 10px; background: #ffffff;">
                <div style="font-size: 11px; color: #059669; font-weight: bold; margin-bottom: 6px;">PMID: {pmid} · {tag_name}</div>
                <h3 style="margin: 0 0 8px 0; color: #0f172a; font-size: 15px; line-height: 1.4;">{title}</h3>
                <p style="margin: 0 0 12px 0; color: #64748b; font-size: 13px; line-height: 1.6;">{abstract}</p>
                <div style="font-size: 12px; color: #475569;">
                    <span>📖 <em>{journal}</em></span> | 
                    <a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/" style="color: #059669; text-decoration: none; font-weight: bold;">查看原文全文 →</a>
                </div>
            </div>"""
                valid_articles_count += 1
        except Exception as e:
            print(f"PubMed XML 数据解析失败: {e}")

# ==================== Step 2: 注入 index.html ====================
if os.path.exists("index.html") and cards_html:
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    pattern = re.compile(
        r"(<!-- AUTO_TRIALS_START -->)(.*?)(<!-- AUTO_TRIALS_END -->)",
        re.DOTALL,
    )
    if pattern.search(content):
        new_content = pattern.sub(f"\\1\n{cards_html}\n<!-- AUTO_TRIALS_END -->", content)
        if new_content != content:
            with open("index.html", "w", encoding="utf-8") as f:
                f.write(new_content)
            print("✅ index.html 临床前沿数据已成功刷新。")
        else:
            print("ℹ️ 内容无变化，跳过文件写入。")
    else:
        print("⚠️ 未在 index.html 中找到 AUTO_TRIALS 插槽注释。")

# ==================== Step 3: Resend 邮件发送（带速率保护） ====================
resend_api_key = os.environ.get("RESEND_API_KEY")
subscribers = []
if os.path.exists("subscribers.txt"):
    with open("subscribers.txt", "r", encoding="utf-8") as f:
        subscribers = list(set([
            line.strip() for line in f.readlines()
            if line.strip() and "@" in line
        ]))

if resend_api_key and subscribers and email_articles_html:
    email_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 620px; margin: 0 auto; padding: 24px; background: #f8fafc; border-radius: 12px;">
        <div style="text-align: center; margin-bottom: 28px;">
            <h1 style="color: #059669; margin: 0; font-size: 22px;">🧬 BioSpan 前沿科研简报</h1>
            <p style="color: #64748b; font-size: 13px; margin-top: 6px;">本周 PubMed 衰老生物学与临床试验前沿精选</p>
        </div>
        {email_articles_html}
        <div style="text-align: center; margin-top: 28px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8;">
            此邮件由 BioSpan 自动化科研机器人发出 · 追踪全球长寿与衰老生物学前沿<br>
            <a href="https://jackqed.github.io/BioSpan/" style="color: #059669; text-decoration: none; margin-top: 6px; display: inline-block;">访问 BioSpan 官方网站</a>
        </div>
    </div>
    """

    print(f"📧 开始向 {len(subscribers)} 位订阅者发送简报...")
    for recipient in subscribers:
        payload = json.dumps({
            "from": "BioSpan News <onboarding@resend.dev>",
            "to": [recipient],
            "subject": "【BioSpan】最新衰老与长寿科研速递",
            "html": email_body,
        }).encode("utf-8")

        resend_headers = {
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json",
        }
        resp = safe_request("https://api.resend.com/emails", headers=resend_headers, data=payload, timeout=10)
        if resp:
            print(f"✅ 邮件已发送至: {recipient}")
        else:
            print(f"❌ 发送至 {recipient} 失败")
        
        # 保护 Resend 免费层速率限制 (2 req/sec)
        time.sleep(0.6)
else:
    print("ℹ️ 未触发邮件发送（缺少 RESEND_API_KEY、无有效订阅者或无新文章）。")
