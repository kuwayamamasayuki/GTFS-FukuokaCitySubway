標準的なバス情報フォーマット出力ツール（西沢ツール）で生成されたファイルは，標準的なバス情報フォーマットでありGTFSとは異なる部分があるため，一部修正する必要があります。

具体的には，以下の修正を加えました。


## 標準的なバス情報フォーマットのみに存在するファイルの削除
* agency_jp.txt
* office_jp.txt

これらについては、標準的なバス情報フォーマットのみに存在するものでありGTFSには不要であるため，削除しました。


## GTFSと標準的なバス情報フォーマットとのデータの使い方の違いによる変更
* stops.txt
* zone_id

標準的なバス情報フォーマット出力ツールでは，zone_idとしてstop_idが自動的に割り当てられるため，駅とホームとで異なるzone_idが割り当てられます。
しかし[googletransitdatafeed - FareExamples.wiki](https://code.google.com/archive/p/googletransitdatafeed/wikis/FareExamples.wiki)のExample 6: Fare depends on station pairs, how you get there doesn't matterでは，「Each station is considered a single zone.」という記載があることから，駅とその駅のホームでは同一のzone_idを用いることとし，その値として駅のstop_idを用いることにしました。


## その他のツールの都合で修正。
* stops.txt
* stop_times.txt

作成したGTFSデータの検証のためにstatic-GTFS-managerというツールを用いましたが，このツールには，trip_id中の「+」文字を空白に読み替えてしまうというバグがあるようです。
本来はそちらのバグを修正すべきでしょうが，とりあえず，ここでは，trips.txt及びstop_times.txt中の「+」文字を削除するという方向で解決しました。
