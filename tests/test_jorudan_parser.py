"""ジョルダンのダイヤ詳細 HTML パーサのテスト。

行先決定ルール:
  * 凡例の「無印=○○」が既定行先（駅により異なる）。無ければ default_destination 引数。
  * 「素の駅名」を値に持つ記号は上書き行先（例 貝=貝塚, 唐=唐津）。
  * 「…で…に接続」等の注記記号は行先を変えず既定のまま（例 ●印, 前●印）。
  * 凡例 dd が無い路線（七隈線）は全便が default_destination（終端）。
"""

from fukuoka_gtfs.verify.jorudan_parser import (
    Departure,
    parse_diagram,
    parse_legend,
)

# 空港線・福岡空港方面（凡例値が「○○ゆき」形式、●印は注記）
AIRPORT_DOWN = """
<html><body>
<ul class="ttArea pc">
  <li class="pc"><dl class="ttBox ttBoxHeader"><dt class="ttToggle"></dt><dd>x</dd></dl></li>
  <li class="pc"><dl class="ttBox">
    <dt class="ttToggle"><span>5</span></dt>
    <dd><ul class="ttList">
      <li class="tooltip linindexlink"><span class="legend">&nbsp;</span><a>30</a></li>
      <li class="tooltip linindexlink"><span class="legend"><font color="#FF0000">貝</font></span><a>45</a></li>
    </ul></dd>
    <dd><ul class="ttList">
      <li class="tooltip linindexlink"><span class="legend"><font>●</font></span><a>50</a></li>
    </ul></dd>
  </dl></li>
</ul>
<ul class="ttArea sp"><li>無視</li></ul>
<div class="legendArea"><dl>
  <dd><span>無印</span>=<font>福岡空港ゆき</font></dd>
  <dd><span><font color="#FF0000">貝</font></span>=<font>貝塚ゆき</font></dd>
  <dd><span><font color="#FF0000">●印</font></span>=中洲川端で貝塚ゆきにのりかえが便利な福岡空港ゆき電車</dd>
</dl></div>
</body></html>
"""

# 空港線・姪浜方面（凡例値が「素の駅名」、前●印は注記、無印=筑前前原）
AIRPORT_UP = """
<html><body>
<ul class="ttArea pc">
  <li class="pc"><dl class="ttBox">
    <dt class="ttToggle"><span>6</span></dt>
    <dd><ul class="ttList">
      <li class="tooltip linindexlink"><span class="legend">&nbsp;</span><a>10</a></li>
      <li class="tooltip linindexlink"><span class="legend">唐</span><a>20</a></li>
      <li class="tooltip linindexlink"><span class="legend">前
                        ●</span><a>30</a></li>
    </ul></dd>
  </dl></li>
</ul>
<div class="legendArea"><dl>
  <dd><span>無印</span>=筑前前原</dd>
  <dd><span>唐</span>=唐津</dd>
  <dd><span>前●印</span>=筑前前原で唐津、西唐津ゆきに接続しています。</dd>
</dl></div>
</body></html>
"""

# 七隈線（凡例 dd 無し）。全便 default_destination。
NANAKUMA = """
<html><body>
<ul class="ttArea pc">
  <li class="pc"><dl class="ttBox">
    <dt class="ttToggle"><span>7</span></dt>
    <dd><ul class="ttList">
      <li class="tooltip linindexlink"><span class="legend">&nbsp;</span><a>05</a></li>
      <li class="tooltip linindexlink"><span class="legend">&nbsp;</span><a>15</a></li>
    </ul></dd>
  </dl></li>
</ul>
<div class="legendArea"><dl></dl></div>
</body></html>
"""


def test_legend_keeps_only_clean_station_entries():
    legend = parse_legend(AIRPORT_DOWN)
    assert legend[""] == "福岡空港"  # 無印（ゆきを除去）
    assert legend["貝"] == "貝塚"
    assert "●" not in legend  # 注記は行先定義ではない


def test_legend_bare_station_values():
    legend = parse_legend(AIRPORT_UP)
    assert legend[""] == "筑前前原"
    assert legend["唐"] == "唐津"
    assert "前●" not in legend  # 注記


def test_default_destination_used_when_no_unmarked_entry():
    # 七隈線は凡例 dd 無し → 全便 default
    deps = parse_diagram(NANAKUMA, default_destination="博多")
    assert deps == [Departure(7, 5, "博多"), Departure(7, 15, "博多")]


def test_airport_down_destinations():
    deps = parse_diagram(AIRPORT_DOWN, default_destination="福岡空港")
    assert Departure(5, 30, "福岡空港") in deps  # 無印
    assert Departure(5, 45, "貝塚") in deps      # 貝
    assert Departure(5, 50, "福岡空港") in deps  # ●印=注記→既定
    assert len(deps) == 3


def test_airport_up_marker_and_annotation():
    deps = parse_diagram(AIRPORT_UP, default_destination="筑前前原")
    assert Departure(6, 10, "筑前前原") in deps  # 無印
    assert Departure(6, 20, "唐津") in deps      # 唐
    assert Departure(6, 30, "筑前前原") in deps  # 前●＝注記→既定
    assert len(deps) == 3


def test_unmarked_entry_overrides_default():
    # 凡例に無印があれば、それが default_destination 引数より優先される
    deps = parse_diagram(AIRPORT_UP, default_destination="無関係")
    assert Departure(6, 10, "筑前前原") in deps


def test_ignores_mobile_area_and_header():
    deps = parse_diagram(AIRPORT_DOWN, default_destination="福岡空港")
    assert len(deps) == 3  # sp領域とttBoxHeaderを拾わない
