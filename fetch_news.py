Python

import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# 1. 向 PubMed 检索最新衰老与长寿相关的顶级科研文献
search_query = "(aging[Title/Abstract] OR longevity[Title/Abstract] OR senolytics[Title/Abstract] OR rapamycin[Title/Abstract] OR NAD+[Title/Abstract]) AND (clinical trial[Filter] OR review[Filter])"
encoded_query = urllib.parse.quote(search_query)
esearch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={encoded_query}&retmax=4&sort=pub_date"

req = urllib.request.Request(esearch_url, headers={"User-Agent": "Mozilla/5.0"})
response = urllib.request.urlopen(req)
tree = ET.fromstring(response.read())
id_list = [id_elem.text for id_elem in tree.findall(".//IdList/Id")]

cards_html = ""

if id_list:
    # 2. 获取具体文献的标题和摘要
    efetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={','.join(id_list)}&retmode=xml"
    fetch_req = urllib.request.Request(efetch_url, headers={"User-Agent": "Mozilla/5.0"})
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
        journal = article.findtext(".//Journal/Title", default="International Journal")

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
else:
    cards_html = "<p class='text-slate-400 text-center col-span-2'>暂未获取到最新论文更新。</p>"

# 3. 替换 index.html 中的动态容器
with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

pattern = re.compile(
    r"(<!-- AUTO_TRIALS_START -->)(.*?)(<!-- AUTO_TRIALS_END -->)", re.DOTALL
)
replacement = f"\\1\n{cards_html}\n            \\3"

new_content = pattern.sub(replacement, content)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(new_content)

print("网页内容已成功自动更新！")
