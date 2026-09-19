"""Import only public committee membership fields from the supplied XLSX."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ALIASES = {'산업통상자원중소벤처기업위원회': 'industry',
           '재정경제기획위원회': 'finance', '기획재정위원회': 'finance',
           '정무위원회': 'affairs'}


def extract(path):
    members = []
    with ZipFile(path) as archive:
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(n.itertext()) for n in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si', NS)]
        for sheet in archive.namelist():
            if not (sheet.startswith('xl/worksheets/sheet') and sheet.endswith('.xml')):
                continue
            for row in ET.fromstring(archive.read(sheet)).findall('.//m:row', NS):
                cells = {}
                for cell in row:
                    column = ''.join(c for c in cell.get('r', '') if c.isalpha())
                    value = cell.find('m:v', NS)
                    cells[column] = shared[int(value.text)] if cell.get('t') == 's' else ''.join(cell.itertext())
                if cells.get('C') in ALIASES:
                    members.append(dict(committee=ALIASES[cells['C']], source_committee=cells['C'],
                                        name=cells['D'], role=cells['B'], party=cells['E'],
                                        constituency=cells['F'], source_cell=f"Sheet0!D{row.get('r')}"))
    keys = [(m['committee'], m['name']) for m in members]
    if len(keys) != len(set(keys)) or set(m['committee'] for m in members) != set(ALIASES.values()):
        raise ValueError('Duplicate membership or missing committee')
    return dict(source_file=Path(path).name, sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                note='사용자 제공 명단 기준. 후보자·장관 자격의 발언은 심사·소관 위원회로 분류하며 의원 소속과 구분.', members=members)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/committee-news/roster.json'))
    args = parser.parse_args()
    args.output.write_text(json.dumps(extract(args.input), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
