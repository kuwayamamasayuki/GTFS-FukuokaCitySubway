.PHONY: setup seed fares verify-fares fetch-jorudan-fares download build validate all publish test clean

PY ?= python

setup:            ## 依存をインストール（編集可能インストール）
	$(PY) -m pip install -e ".[dev]"

seed:             ## reference_gtfs/ を 2019 年版から再生成（通常は不要）
	$(PY) scripts/seed_reference.py

fares:            ## 運賃(fare_*)を公式運賃表(PDF)から抽出して再生成
	$(PY) scripts/verify_fares.py --write

verify-fares:     ## 現行運賃を公式運賃表(PDF)と全ペア突き合わせ(読み取りのみ)
	$(PY) scripts/verify_fares.py

fetch-jorudan-fares: ## ジョルダン運賃を取得し突合用フィクスチャを更新(Issue #10)
	$(PY) scripts/fetch_jorudan_fares.py

download:         ## 時刻表 Excel を取得
	$(PY) -m fukuoka_gtfs.cli download

build:            ## GTFS を生成（build/feed.zip）
	$(PY) -m fukuoka_gtfs.cli build

validate:         ## 生成済み GTFS を検証（Canonical + Python）
	$(PY) -m fukuoka_gtfs.cli validate --download-tools

all:              ## download → build → validate
	$(PY) -m fukuoka_gtfs.cli all --download-tools

publish: build    ## 生成した GTFS を dist/ に公開スナップショットとして配置
	rm -rf dist && mkdir -p dist
	cp build/gtfs/*.txt dist/
	cp build/feed.zip dist/FukuokaCitySubway.zip

test:             ## テスト
	$(PY) -m pytest -q

clean:
	rm -rf build
