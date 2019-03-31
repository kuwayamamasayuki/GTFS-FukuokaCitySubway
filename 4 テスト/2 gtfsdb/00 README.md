平日／土休別，駅別に時刻表情報を表示し，元データと比較する。


## テスト概要
平日／土休別，駅別に時刻表情報を表示する。
それを，元データと*目視で*比較する。

## 判定基準
元データと差がなければ合格とする。
（どこまで細かく見るかはテスト実施者にまかせる。）

## テスト詳細
* （PostgreSQL等のDBMSがインストールされていなければ）DBMSをインストールする。
* （gtfsdbがインストールされていなければ）gtfsdbをインストールする。
README.rstに従い，
```
git clone https://github.com/OpenTransitTools/gtfsdb.git
cd gtfsdb
buildout install prod postgresql
```
* GTFSデータを読み込む。
```
bin/gtfsdb-load  --database_url postgresql://postgres@localhost:5432  ../../../FukuokaCitySubway-20190316.zip 
```
* psqlでデータを抽出
```
psql -U postgres -f timetable.sql -o /tmp/out.txt
***
* 出力したout.txtは，平日／土休，駅名，出発時刻の順に並んでいるので，
これを元データと比較する。（ソート順の関係で10時から始まっているので，必要に応じて並べ替えること。）

