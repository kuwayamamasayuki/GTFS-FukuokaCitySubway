"""ジョルダンのダイヤ詳細 HTML パーサのテスト。

HTML はジョルダンの実ページ（diagramdtl）の構造をそのまま縮約したもの。
凡例ブロックと、時刻表本体（ttArea pc）に時・分・行先記号・複数ホームを含む。
"""

from fukuoka_gtfs.verify.jorudan_parser import (
    Departure,
    parse_diagram,
    parse_legend,
)

# 空港線・姪浜駅・福岡空港方面の実ページを縮約した HTML。
# - 凡例: 無印=福岡空港ゆき / 貝=貝塚ゆき / ●印=…福岡空港ゆき電車
# - 5 時台: 1,2 番ホームに 30(無印) と 45(貝), 3 番ホームに 35(貝)
# - 0 時台: 1,2 番ホームに 00(無印), 3 番ホームに 25(●= 福岡空港)
SAMPLE_HTML = """
<html><body>
<ul class="ttArea pc">
  <li class="pc"><dl class="ttBox ttBoxHeader">
    <dt class="ttToggle"></dt><dd>1,2番ホームから</dd><dd>3番ホームから</dd>
  </dl></li>
  <li class="pc"><dl class="ttBox">
    <dt class="ttToggle"><span>5</span></dt>
    <dd><ul class="ttList">
      <li class="tooltip linindexlink">
        <span class="legend"> &nbsp; </span>
        <a href="javascript:void(0);">30</a>
        <input type="hidden" value="464507;;30" class="lineindex" />
      </li>
      <li class="tooltip linindexlink">
        <span class="legend"> <font color="#FF0000">貝</font> </span>
        <a href="javascript:void(0);">45</a>
        <input type="hidden" value="105977467;;45" class="lineindex" />
      </li>
    </ul></dd>
    <dd><ul class="ttList">
      <li class="tooltip linindexlink">
        <span class="legend"> <font color="#FF0000">貝</font> </span>
        <a href="javascript:void(0);">35</a>
        <input type="hidden" value="105715323;;35" class="lineindex" />
      </li>
    </ul></dd>
  </dl></li>
  <li class="pc"><dl class="ttBox">
    <dt class="ttToggle"><span>0</span></dt>
    <dd><ul class="ttList">
      <li class="tooltip linindexlink">
        <span class="legend"> &nbsp; </span>
        <a href="javascript:void(0);">00</a>
        <input type="hidden" value="9770619;;00" class="lineindex" />
      </li>
    </ul></dd>
    <dd><ul class="ttList">
      <li class="tooltip linindexlink">
        <span class="legend"> <font color="#FF0000">●</font> </span>
        <a href="javascript:void(0);">25</a>
        <input type="hidden" value="116594299;;25" class="lineindex" />
      </li>
    </ul></dd>
  </dl></li>
</ul>
<ul class="ttArea sp"><li>(モバイル用は無視されること)</li></ul>
<div class="titleTxt mb8 borderD">凡例</div>
<div class="legendArea"><dl>
  <dd> <span><font color="">無印</font></span>=<font color="">福岡空港ゆき</font> </dd>
  <dd> <span><font color="#FF0000">貝</font></span>=<font color="">貝塚ゆき</font> </dd>
  <dd> <span><font color="#FF0000">●印</font></span>=<font color="">中洲川端で貝塚ゆきにのりかえが便利な福岡空港ゆき電車</font> </dd>
</dl></div>
</body></html>
"""


def test_parse_legend_maps_markers_to_final_destinations():
    legend = parse_legend(SAMPLE_HTML)
    assert legend[""] == "福岡空港"  # 無印 = 既定行先
    assert legend["貝"] == "貝塚"
    # ●印 は説明文だが最終行先は福岡空港
    assert legend["●"] == "福岡空港"


def test_parse_diagram_extracts_all_departures_with_destinations():
    deps = parse_diagram(SAMPLE_HTML)
    assert Departure(hour=5, minute=30, destination="福岡空港") in deps
    assert Departure(hour=5, minute=45, destination="貝塚") in deps
    assert Departure(hour=5, minute=35, destination="貝塚") in deps  # 3 番ホーム統合
    assert Departure(hour=0, minute=0, destination="福岡空港") in deps
    assert Departure(hour=0, minute=25, destination="福岡空港") in deps  # ●


def test_parse_diagram_merges_platforms_and_counts():
    deps = parse_diagram(SAMPLE_HTML)
    # 全ホーム統合で 5 便（5 時台 3 便 + 0 時台 2 便）
    assert len(deps) == 5


def test_parse_diagram_ignores_mobile_area():
    # sp(モバイル)領域の li を時刻として拾わないこと
    deps = parse_diagram(SAMPLE_HTML)
    assert all(isinstance(d.minute, int) for d in deps)
    assert len(deps) == 5
