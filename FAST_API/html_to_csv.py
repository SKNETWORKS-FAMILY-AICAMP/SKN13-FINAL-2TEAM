# -*- coding: utf-8 -*-
import os
import csv
import chardet
from bs4 import BeautifulSoup
from tqdm import tqdm  # 진행상황 표시용

html_dir = 'C:\SKN13_Documnet\SKN13_Final_Project\지민_개인작업폴더\html_files'
output_csv = 'products.csv'

fieldnames = ['상품명', '브랜드', '소재', '치수정보', '색상옵션', '사이즈옵션', '가격', '세탁법', '대표이미지URL']

def read_file_auto_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw = f.read()
    detected = chardet.detect(raw)
    encoding = detected['encoding'] if detected['encoding'] else 'utf-8'
    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        # 디코딩 실패 시 utf-8로 강제 디코딩(오류 무시)
        return raw.decode('utf-8', errors='ignore')

def extract_product_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    product = {}

    # 상품명
    title_tag = soup.find('h3', class_='product')
    product['상품명'] = title_tag.get_text(strip=True) if title_tag else ''

    # 브랜드
    brand_tag = soup.find('h2', class_='brand')
    product['브랜드'] = brand_tag.get_text(strip=True) if brand_tag else ''

    # 소재 (table 내 소재 행)
    material = ''
    table = soup.find('table')
    if table:
        for row in table.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            if th and '소재' in th.get_text():
                material = td.get_text(strip=True) if td else ''
                break
    product['소재'] = material

    # 치수정보 (table 내 치수 관련 행 전부 추출)
    size_info = {}
    if table:
        for row in table.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            if th and td:
                key = th.get_text(strip=True)
                if any(x in key for x in ['가슴', '소매', '어깨', '길이', '밑단']):
                    size_info[key] = td.get_text(strip=True)
    product['치수정보'] = '; '.join([f'{k}:{v}' for k, v in size_info.items()])

    # 색상옵션, 사이즈옵션 (select/option 태그에서 추출)
    colors = []
    sizes = []
    for select in soup.find_all('select'):
        select_name = (select.get('name') or '') + (select.get('id') or '')
        options = select.find_all('option')
        option_texts = [o.get_text(strip=True) for o in options if o.get_text(strip=True)]
        if 'color' in select_name.lower():
            colors += option_texts
        elif 'size' in select_name.lower():
            sizes += option_texts
    product['색상옵션'] = ', '.join(colors)
    product['사이즈옵션'] = ', '.join(sizes)

    # 가격 (dl.price 또는 div.price_wrap 내부 텍스트)
    price = ''
    dl_price = soup.find('dl', class_='price')
    if dl_price:
        price = dl_price.get_text(separator=' ', strip=True)
    else:
        div_price = soup.find('div', class_='price_wrap')
        if div_price:
            price = div_price.get_text(separator=' ', strip=True)
    product['가격'] = price

    # 세탁법 (strong, b 태그 중 '세탁' 키워드 포함 영역 텍스트)
    washing = ''
    for strong in soup.find_all(['strong', 'b']):
        text = strong.get_text()
        if any(x in text for x in ['세탁', '세탁법', '주의']):
            parent = strong.parent
            if parent:
                washing = parent.get_text(strip=True)
                break
    product['세탁법'] = washing

    # 대표 이미지 URL (div.img_goods img src)
    img_tag = soup.select_one('div.img_goods img')
    product['대표이미지URL'] = img_tag['src'] if img_tag and img_tag.has_attr('src') else ''

    return product


if __name__ == '__main__':
    html_files = [f for f in os.listdir(html_dir) if f.endswith('.html')]

    with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for filename in tqdm(html_files, desc='Processing HTML files'):
            file_path = os.path.join(html_dir, filename)
            html_content = read_file_auto_encoding(file_path)
            product_info = extract_product_info(html_content)
            writer.writerow(product_info)

    print("완료: products.csv에 데이터 저장됨")
