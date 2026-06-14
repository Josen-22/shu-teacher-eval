import requests
from bs4 import BeautifulSoup
import time
import json
import os
import re
import sys

BASE_URL = "https://ms.shu.edu.cn"
DIR_URL = "https://ms.shu.edu.cn/jsyyj/jsml.htm"

def load_external_teacher_names():
    path = os.path.join(os.path.dirname(__file__), "external_teachers.json")
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {str(x).strip() for x in data if str(x).strip()}
    except Exception:
        return set()
    return set()

def log(msg):
    with open('scraper.log', 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
    print(msg)

def get_teacher_links():
    try:
        response = requests.get(DIR_URL)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        external_names = load_external_teacher_names()
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/info/' in href and '.htm' in href:
                name_text = (a.get_text() or '').strip()
                if name_text in external_names:
                    continue
                clean_href = href.replace('../', '/')
                if not clean_href.startswith('/'):
                    clean_href = '/' + clean_href
                full_url = BASE_URL + clean_href
                if full_url not in links:
                    links.append(full_url)
        return links
    except Exception as e:
        log(f"Error getting teacher links: {e}")
        return []

def scrape_teacher_details(url):
    try:
        response = requests.get(url, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        name = ""
        title = ""
        department = ""
        email = ""
        research = ""
        courses = []
        bio = ""

        page_title = soup.title.string if soup.title else ""
        if page_title:
            name = page_title.split('-')[0].strip()

        content_div = soup.find(class_="v_news_content") or soup.find("div", {"id": "vsb_content"})
        if not content_div:
            content_div = soup.body

        text_nodes = [s.strip() for s in content_div.strings if s.strip()]
        all_text = " ".join(text_nodes)

        mailto = soup.select_one('a[href^="mailto:"]')
        if mailto and mailto.get('href'):
            email = mailto.get('href').replace('mailto:', '').strip()

        email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', all_text)
        if email_match:
            email = email_match.group(0)

        email_label_match = re.search(r'Email[:：]\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', all_text, re.IGNORECASE)
        if email_label_match:
            email = email_label_match.group(1).strip()

        for i, node in enumerate(text_nodes):
            if not name and i < 5 and len(node) < 10:
                name = node
            
            if any(label in node for label in ['系所：', '系：', '所在部门：', '学系：']):
                department = node.split('：')[-1].strip() or (text_nodes[i+1] if i+1 < len(text_nodes) else "")
            elif any(label in node for label in ['职称：', '职 称：', '职务：']):
                title = node.split('：')[-1].strip() or (text_nodes[i+1] if i+1 < len(text_nodes) else "")
            elif any(label in node for label in ['研究方向：', '研究领域：', '研究兴趣：', '主要研究方向：']):
                found_research = node.split('：')[-1].strip() or (text_nodes[i+1] if i+1 < len(text_nodes) else "")
                if len(found_research) > len(research):
                    research = found_research
            elif any(label in node for label in ['主讲课程：', '讲授课程：', '本科生课程：', '课程名称：', '讲授课程', '所授课程']):
                courses_str = node.split('：')[-1].strip() or (text_nodes[i+1] if i+1 < len(text_nodes) else "")
                courses_str = courses_str.replace('《', '').replace('》', '')
                courses_str = re.sub(r'等[。，]?$', '', courses_str)
                parts = [c.strip() for c in re.split(r'[、,，;；\s]', courses_str) if c.strip()]
                valid_courses = [p for p in parts if 2 <= len(p) <= 20 and not any(j in p for j in ['Journal', 'Review', '学报', '研究', '杂志'])]
                courses.extend(valid_courses)
            elif any(label in node for label in ['个人简介：', '个人简况：']) or node == '个人简介':
                bio_parts = []
                # Remove '核心研究方向' from stop_headers to include it in bio
                stop_headers = ['科研', '服务', '教学', '团队', '爱好', '座右铭', '上一条', '下一条', '联系方式', '主讲课程', '讲授课程']
                for j in range(i + 1, min(i + 30, len(text_nodes))):
                    next_node = text_nodes[j]
                    if any(header in next_node for header in stop_headers) and (len(next_node) < 15 or next_node.endswith('：')):
                        break
                    if len(next_node) < 10 and next_node.endswith('：') and not any(h in next_node for h in ['研究', '简介']):
                        break
                    bio_parts.append(next_node)
                bio = "\n".join(bio_parts)[:2000]

        if not department:
            dept_match = re.search(r'(管理科学与工程系|工商管理系|会计系|信息管理系)', all_text)
            if dept_match:
                department = dept_match.group(1)
            else:
                dept_match2 = re.search(r'管理学院\s*([^\s，,。；;]{2,20}系)', all_text)
                if dept_match2:
                    department = dept_match2.group(1)

        if not research:
            m = re.search(
                r'(研究方向|研究领域|研究兴趣|主要研究方向)[:：]\s*(.+?)(?=(研究兴趣|个人简介|教育背景|工作经历|代表性研究成果|科研项目|Email|邮箱|办公室)[:：]|$)',
                all_text,
                re.IGNORECASE,
            )
            if m:
                research = m.group(2).strip()[:500]

        if not bio:
            m = re.search(
                r'(个人简介|个人简况)[:：]\s*(.+?)(?=(教育背景|工作经历|代表性研究成果|科研项目|其他)[:：]|$)',
                all_text,
                re.IGNORECASE,
            )
            if m:
                bio = m.group(2).strip()[:2000]

        if not title:
            for node in text_nodes[:15]:
                matches = re.findall(r'(教授|讲师|副教授|研究员|助教|博导|硕导)', node)
                if matches:
                    title = "、".join(set(matches))
                    break

        if not courses:
            for node in text_nodes:
                if '《' in node and '》' in node:
                    matches = re.findall(r'《(.*?)》', node)
                    if 1 < len(matches) < 15:
                        courses.extend([m.strip() for m in matches if 2 <= len(m) <= 25])
        
        if department and len(department) > 50:
            department = department[:50]

        return {
            "name": name,
            "url": url,
            "title": title or "教师",
            "department": department,
            "email": email,
            "research": research,
            "courses": list(dict.fromkeys(courses)),
            "bio": bio
        }
    except Exception as e:
        log(f"Error scraping {url}: {e}")
        return None

def run_scraper(limit=None):
    if os.path.exists('scraper.log'):
        os.remove('scraper.log')
    log("Starting scraper...")
    links = get_teacher_links()
    log(f"Found {len(links)} teacher links.")
    
    if limit:
        links = links[:limit]
        log(f"Limiting to first {limit} teachers for speed.")
    
    teachers_data = []
    for i, link in enumerate(links):
        log(f"Scraping ({i+1}/{len(links)}): {link}")
        data = scrape_teacher_details(link)
        if data and data['name']:
            teachers_data.append(data)
        time.sleep(0.1)
            
    output_path = os.path.join(os.path.dirname(__file__), 'teachers.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(teachers_data, f, ensure_ascii=False, indent=2)
    log(f"Scraper finished. Saved {len(teachers_data)} teachers to {output_path}")

if __name__ == "__main__":
    run_scraper(limit=50)
