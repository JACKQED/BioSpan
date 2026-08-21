import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# 1. 向 PubMed 检索最新衰老与长寿科研文献
search_query = "(aging[Title/Abstract] OR longevity[Title/Abstract] OR senolytics[Title/Abstract] OR rapamycin[Title/Abstract] OR NAD+[Title/Abstract]) AND (clinical trial[Filter] OR review[Filter])"
encoded_query = urllib.parse.quote(search_query)
esearch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={encoded_query}&retmax=4&sort=pub_date"

req = urllib.request.Request(esearch_url, headers={"User-Agent": "Mozilla/5.0"})
response = urllib.request.urlopen(req)
tree = ET.fromstring(response.read())
id_list = [id_elem.text for id_elem in tree.findall(".//IdList/Id")]

cards_html = ""
email_articles_html = ""

if id_list:
    efetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={','.join(id_list)}&retmode=xml"
    fetch_req = urllib.request.Request(
        efetch_url, headers={"User-Agent": "Mozilla/5.0"}
    )
    fetch_res = urllib.request.urlopen(fetch_req)
    fetch_tree = ET.fromstring(fetch_res.read())

    for article in fetch_tree.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID")
        title = article.findtext(".//ArticleTitle", default="最新衰老机制研究")
        abstract_elem = article.find(".//AbstractText")
        abstract = (
            abstract_elem.text[:180] + "..."
            if (abstract_elem is not None and abstract_elem.text)
            else "该论文详细探讨了衰老分子靶点、代谢调控或延寿化合物的最新机制与临床前验证。"
        )
        journal = article.findtext(
            ".//Journal/Title", default="International Journal"
        )

        # 网页卡片 HTML
        cards_html += f"""
            <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl hover:border-emerald-500/40 transition flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between mb-3">
                        <span class="text-xs font-semibold px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">PubMed 实时追踪</span>
                        <span class="text-xs text-slate-500">PMID: {pmid}</span>
                    </div>
                    <h3 class="text-base font-bold text-white mb-2 line-clamp-2">{title}</h3>
                    <p class="text-slate-400 text-xs leading-relaxed mb-4">{abstract}</p>
                </div>
                <div class="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs">
                    <span class="text-slate-400 truncate max-w-[180px]"><i class="fa-solid fa-book-journal-whills mr-1 text-emerald-400"></i> {journal}</span>
                    <a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/" target="_blank" class="text-emerald-400 hover:text-emerald-300 font-medium">查看原文 →</a>
                </div>
            </div>"""

        # 邮件内容 HTML
        email_articles_html += f"""
            <div style="margin-bottom: 24px; padding: 16px; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff;">
                <h3 style="margin: 0 0 8px 0; color: #0f172a; font-size: 16px;">{title}</h3>
                <p style="margin: 0 0 12px 0; color: #64748b; font-size: 13px; line-height: 1.5;">{abstract}</p>
                <div style="font-size: 12px; color: #059669;">
                    <span>期刊: {journal}</span> | 
                    <a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/" style="color: #10b981; text-decoration: none; font-weight: bold;">查看原文 →</a>
                </div>
            </div>"""

# 2. 更新 index.html
if os.path.exists("index.html") and cards_html:
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(
        r"(<!-- AUTO_TRIALS_START -->)(.*?)(<!-- AUTO_TRIALS_END -->)",
        re.DOTALL,
    )
    new_content = pattern.sub(f"\\1\n{cards_html}\n            \\3", content)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("网页内容更新完成。")

# 3. 自动发送 Newsletter 邮件
resend_api_key = os.environ.get("RESEND_API_KEY")
subscribers = []
if os.path.exists("subscribers.txt"):
    with open("subscribers.txt", "r", encoding="utf-8") as f:
        subscribers = [
            line.strip()
            for line in f.readlines()
            if line.strip() and "@" in line
        ]

if resend_api_key and subscribers and email_articles_html:
    email_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f8fafc;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #059669; margin: 0;">BioSpan 前沿科研简报</h1>
            <p style="color: #64748b; font-size: 14px; margin-top: 4px;">本期 PubMed 衰老与长寿领域精选文献更新</p>
        </div>
        {email_articles_html}
        <div style="text-align: center; margin-top: 24px; font-size: 12px; color: #94a3b8;">
            此邮件由 BioSpan 自动化科研机器人发出，每天追踪最新临床前沿。
        </div>
    </div>
    """

    for recipient in subscribers:
        payload = json.dumps(
            {
                "from": "BioSpan News <onboarding@resend.dev>",
                "to": [recipient],
                "subject": "【BioSpan】最新衰老与长寿科研速递",
                "html": email_body,
            }
        ).encode("utf-8")

        mail_req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
        )
        try:
            with urllib.request.urlopen(mail_req) as resp:
                print(f"邮件已成功发送至: {recipient}")
        except Exception as e:
            print(f"发送至 {recipient} 失败: {e}")
