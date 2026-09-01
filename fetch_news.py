import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# 1. 精准化 PubMed 检索词（聚焦人类/哺乳动物医学、衰老生物学、抗衰靶点，排除植物与兽医）
search_query = (
    '("Longevity"[Mesh] OR "Aging"[Mesh] OR "Geroscience"[tiab] OR "Senolytics"[tiab] OR '
    '"Rapamycin"[tiab] OR "Metformin"[tiab] OR "NAD+"[tiab] OR "cellular senescence"[tiab]) AND '
    '("Clinical Trial"[Publication Type] OR "Randomized Controlled Trial"[Publication Type] OR "Review"[Publication Type] OR "humans"[MeSH Terms]) '
    'NOT ("Plants"[Mesh] OR "Plant"[tiab] OR "Veterinary"[tiab] OR "Agriculture"[tiab])'
)

encoded_query = urllib.parse.quote(search_query)
esearch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={encoded_query}&retmax=4&sort=pub_date"

req = urllib.request.Request(esearch_url, headers={"User-Agent": "BioSpan-Bot/1.0 (https://jackqed.github.io/BioSpan/)"})
try:
    with urllib.request.urlopen(req, timeout=15) as response:
        tree = ET.fromstring(response.read())
        id_list = [id_elem.text for id_elem in tree.findall(".//IdList/Id") if id_elem.text]
except Exception as e:
    print(f"PubMed ID 检索失败: {e}")
    id_list = []

cards_html = ""
email_articles_html = ""


def get_full_text(element):
    """递归提取 XML 元素下的所有文本，包含内联 HTML 标签"""
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def detect_topic_tag(text):
    """根据标题/摘要内容自动匹配分类标签与颜色"""
    t = text.lower()
    if any(k in t for k in ["rapamycin", "mtor", "autophagy"]):
        return "mTOR / 雷帕霉素", "bg-purple-500/10 text-purple-400 border-purple-500/20"
    if any(k in t for k in ["senolytic", "senescence", "dasatinib", "quercetin", "sasp"]):
        return "Senolytics / 清除衰老细胞", "bg-rose-500/10 text-rose-400 border-rose-500/20"
    if any(k in t for k in ["nad+", "nmn", "nr", "sirtuin", "mitochondria"]):
        return "NAD+ / 线粒体代谢", "bg-blue-500/10 text-blue-400 border-blue-500/20"
    if any(k in t for k in ["gut", "microbiome", "microbiota"]):
        return "肠道菌群 / 免疫衰老", "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
    if any(k in t for k in ["metformin", "ampk", "glucose"]):
        return "AMPK / 代谢干预", "bg-teal-500/10 text-teal-400 border-teal-500/20"
    return "衰老生物学前沿", "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"


if id_list:
    efetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={','.join(id_list)}&retmode=xml"
    fetch_req = urllib.request.Request(efetch_url, headers={"User-Agent": "BioSpan-Bot/1.0"})
    
    try:
        with urllib.request.urlopen(fetch_req, timeout=20) as fetch_res:
            fetch_tree = ET.fromstring(fetch_res.read())
            
            for article in fetch_tree.findall(".//PubmedArticle"):
                pmid = article.findtext(".//PMID", default="")
                
                # 提取完整标题（处理带标签的标题）
                title_elem = article.find(".//ArticleTitle")
                title_raw = get_full_text(title_elem) if title_elem is not None else "最新衰老机制与干预研究"
                title = html.escape(title_raw.rstrip("."))
                
                # 提取完整结构化摘要
                abstract_nodes = article.findall(".//AbstractText")
                if abstract_nodes:
                    full_abstract = " ".join([get_full_text(node) for node in abstract_nodes])
                    abstract_clean = re.sub(r"\s+", " ", full_abstract).strip()
                    abstract = html.escape(abstract_clean[:200] + "..." if len(abstract_clean) > 200 else abstract_clean)
                else:
                    abstract = "该同行评审论文详细探讨了衰老分子靶点、代谢调控或延寿化合物的最新作用机制与临床验证。"
                
                journal_elem = article.find(".//Journal/Title")
                journal_raw = get_full_text(journal_elem) if journal_elem is not None else "Peer-Reviewed Journal"
                journal = html.escape(journal_raw)

                # 智能分类标签
                tag_name, tag_style = detect_topic_tag(title_raw + " " + abstract)

                # 网页展示卡片 HTML
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

                # 邮件通知卡片 HTML
                email_articles_html += f"""
            <div style="margin-bottom: 20px; padding: 16px; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff;">
                <div style="font-size: 11px; color: #059669; font-weight: bold; margin-bottom: 6px;">PMID: {pmid} · {tag_name}</div>
                <h3 style="margin: 0 0 8px 0; color: #0f172a; font-size: 15px; line-height: 1.4;">{title}</h3>
                <p style="margin: 0 0 12px 0; color: #64748b; font-size: 13px; line-height: 1.6;">{abstract}</p>
                <div style="font-size: 12px; color: #475569; display: flex; justify-content: space-between;">
                    <span>📖 期刊: <em>{journal}</em></span>
                    <a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/" style="color: #059669; text-decoration: none; font-weight: bold;">阅读论文全文 →</a>
                </div>
            </div>"""
    except Exception as e:
        print(f"PubMed 数据拉取与解析失败: {e}")

# 2. 更新 index.html
if os.path.exists("index.html") and cards_html:
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    pattern = re.compile(
        r"(<!-- AUTO_TRIALS_START -->)(.*?)(<!-- AUTO_TRIALS_END -->)",
        re.DOTALL,
    )
    if pattern.search(content):
        new_content = pattern.sub(f"\\1\n{cards_html}\n            \\3", content)
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(new_content)
        print("✅ index.html 临床前沿数据已成功刷新。")
    else:
        print("⚠️ 未在 index.html 中找到 AUTO_TRIALS 插槽注释。")

# 3. 自动发送 Newsletter 邮件
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

    for recipient in subscribers:
        payload = json.dumps({
            "from": "BioSpan News <onboarding@resend.dev>",
            "to": [recipient],
            "subject": "【BioSpan】最新衰老与长寿科研速递",
            "html": email_body,
        }).encode("utf-8")

        mail_req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "BioSpan-Bot/1.0",
            },
        )
        try:
            with urllib.request.urlopen(mail_req, timeout=10) as resp:
                print(f"✅ 邮件已成功发送至: {recipient}")
        except Exception as e:
            print(f"❌ 发送至 {recipient} 失败: {e}")
else:
    print("ℹ️ 未触发邮件发送（缺少 API KEY、无订阅者或无新文章）。")
