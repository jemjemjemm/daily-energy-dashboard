#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_generate_html_tooltip.py

현재 daily-energy-dashboard의 scripts/generate_html_report.py에서 비어 있는
TOOLTIP_SCRIPT 블록을 실제 mouse/touch/pointer tooltip 스크립트로 교체합니다.

적용 대상:
- scripts/generate_html_report.py

효과:
- 원유/석유제품 그래프에 마우스를 올리면 해당 날짜 가격 표시
- iPhone Safari/모바일에서는 그래프 터치·드래그 시 해당 날짜 가격 표시
- 기존 데이터 수집, 뉴스 수집, 가격 병합, report-index 생성 로직은 변경하지 않음
"""
from __future__ import annotations

import re
from pathlib import Path

TARGET = Path("scripts/generate_html_report.py")

TOOLTIP_SCRIPT = r'''<script>
(function(){
  'use strict';

  function parseChartConfig(box){
    if(!box) return null;
    var raw = box.getAttribute('data-chart');
    if(!raw) return null;
    try { return JSON.parse(raw); }
    catch(e) { return null; }
  }

  function valueText(value){
    if(value === null || value === undefined || value === '' || value === 0) return '-';
    var n = Number(value);
    return Number.isFinite(n) ? n.toFixed(2) : '-';
  }

  function clamp(n, min, max){
    return Math.max(min, Math.min(max, n));
  }

  function clientPoint(evt){
    if(evt && evt.touches && evt.touches.length) {
      return {x: evt.touches[0].clientX, y: evt.touches[0].clientY};
    }
    if(evt && evt.changedTouches && evt.changedTouches.length) {
      return {x: evt.changedTouches[0].clientX, y: evt.changedTouches[0].clientY};
    }
    return {x: evt.clientX, y: evt.clientY};
  }

  function initChart(box){
    var cfg = parseChartConfig(box);
    if(!cfg || !cfg.data || !cfg.data.length) return;

    var svg = box.querySelector('svg');
    var line = box.querySelector('.chart-hover-line');
    var tip = box.querySelector('.chart-tooltip');
    if(!svg || !tip) return;

    var W = Number(cfg.width || 440);
    var left = Number(cfg.left || 38);
    var right = Number(cfg.right || 10);
    var top = Number(cfg.top || 16);
    var bottomY = Number(cfg.bottomY || 198);
    var pw = W - left - right;
    var keys = cfg.keys || [];
    var data = cfg.data || [];

    function show(evt){
      var pt = clientPoint(evt);
      if(pt.x === undefined || pt.y === undefined) return;

      var rect = box.getBoundingClientRect();
      if(!rect || !rect.width) return;

      var relX = (pt.x - rect.left) / rect.width * W;
      relX = clamp(relX, left, W - right);

      var idx = 0;
      if(data.length > 1) {
        idx = Math.round((relX - left) / pw * (data.length - 1));
        idx = clamp(idx, 0, data.length - 1);
      }

      var row = data[idx] || {};
      var xx = left + (data.length <= 1 ? 0 : idx / (data.length - 1) * pw);

      if(line) {
        line.setAttribute('x1', String(xx));
        line.setAttribute('x2', String(xx));
        line.setAttribute('y1', String(top));
        line.setAttribute('y2', String(bottomY));
        line.setAttribute('opacity', '0.45');
        line.style.opacity = '0.45';
      }

      var html = '<div class="date">' + (row.label || row.date || '') + '</div>';
      keys.forEach(function(pair){
        var key = pair[0];
        var label = pair[1] || pair[0];
        html += '<div class="tooltip-row"><span>' + label + '</span><b>' + valueText(row[key]) + '</b></div>';
      });
      tip.innerHTML = html;
      tip.style.display = 'block';

      var localX = pt.x - rect.left;
      var localY = pt.y - rect.top;
      var tw = tip.offsetWidth || 150;
      var th = tip.offsetHeight || 104;
      var leftPos = localX + 12;
      var topPos = localY - 10;

      if(leftPos + tw > rect.width) leftPos = localX - tw - 12;
      if(leftPos < 4) leftPos = 4;
      if(topPos + th > rect.height) topPos = rect.height - th - 4;
      if(topPos < 4) topPos = 4;

      tip.style.left = leftPos + 'px';
      tip.style.top = topPos + 'px';
    }

    function hide(){
      if(line) {
        line.setAttribute('opacity', '0');
        line.style.opacity = '0';
      }
      tip.style.display = 'none';
    }

    box.addEventListener('mousemove', show, {passive:true});
    box.addEventListener('mouseleave', hide, {passive:true});
    box.addEventListener('click', show, {passive:true});
    box.addEventListener('touchstart', show, {passive:true});
    box.addEventListener('touchmove', show, {passive:true});
    box.addEventListener('touchend', function(){}, {passive:true});

    if(window.PointerEvent) {
      box.addEventListener('pointerdown', show, {passive:true});
      box.addEventListener('pointermove', show, {passive:true});
      box.addEventListener('pointerleave', hide, {passive:true});
    }
  }

  function init(){
    var boxes = document.querySelectorAll('.chart-box[data-chart]');
    for(var i=0; i<boxes.length; i++) initChart(boxes[i]);
  }

  if(document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
</script>'''


def main() -> int:
    if not TARGET.exists():
        raise FileNotFoundError(f"대상 파일을 찾을 수 없습니다: {TARGET}")

    text = TARGET.read_text(encoding="utf-8")

    pattern = re.compile(r'TOOLTIP_SCRIPT\s*=\s*r?""".*?"""\.strip\(\)', re.DOTALL)
    replacement = 'TOOLTIP_SCRIPT = r"""\n' + TOOLTIP_SCRIPT + '\n""".strip()'

    new_text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("TOOLTIP_SCRIPT 블록을 정확히 1개 찾지 못했습니다. generate_html_report.py를 확인하세요.")

    if new_text == text:
        print("[SKIP] 변경 사항 없음")
        return 0

    TARGET.write_text(new_text, encoding="utf-8")
    print(f"[OK] TOOLTIP_SCRIPT 복원 완료: {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
