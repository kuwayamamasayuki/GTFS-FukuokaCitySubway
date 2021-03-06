このフォルダにあるExcelファイルは，元データを，「標準的なバス情報フォーマット出力ツール」の時刻表ワークシートに貼り付けやすい形に変形するためのツールです。

使い方は，以下の通りです。


1. （平日　空港貝塚方面），（土休　空港貝塚方面），（平日　姪浜方面）及び（土休　姪浜方面）の各シートにおいて，人間が見やすいように二段組になっているが，コンピュータで処理しやすいように一段組とする。
すなわち，下の段を上の段の右側に移動させる。

1. 標準的なバス情報フォーマット出力ツールにおいて，平日と土休はまとめて処理できるで，一枚のシートにまとめる（平日の右側に土休の分を移動させる）。

1. １～４１行目の部分をコピー（あるいは行ごと挿入）。
この際，「平日」「土休」等，薄緑色になっているところは手入力なので注意（特に「土休」）。
また，空港線と箱崎線で式が異なる部分（オレンジ色部分）があるので要注意！
さらに，空港・貝塚方面行きと姪浜方面行きでも式が異なる部分があるので要注意！

1. 新たにシートを作成し（ここでは，「tmp（空港貝塚方面）」等とした。）し，元のシートの１～４１行目の部分を、「形式を選択して貼り付け」する。
この際，「値のみ」とすることと「行／列の入れ替え」を選択することを忘れないこと！

1. 新たに作成した方のシートで，「データ」の「フィルター」をかけ，「空港線」，「箱崎線」それぞれのみを表示させる。
空港線のみを表示させる場合には，祇園か博多駅の列で，空白でない行を選択する。
空港線で箱崎線連絡のみのものを表示させる場合には，まず呉服町から貝塚駅の適当な列で空白でない行を選択し，
その後，空港線の駅の適当な列で空白でない行を選択する。
箱崎線のみを表示させる場合には，呉服町駅から貝塚駅の適当な列で，空白でない行を選択する。

1. 空港線のみを表示させた場合は，右側の方に箱崎線の駅の時刻が表示されているので，そこを除く形で領域を選択し，標準的なバス情報フォーマット出力ツールの時刻表ワークシートに、形式を選択して貼り付ける。
この際には，また「行／列の入れ替え」を選択する。
箱崎線のみを表示させた場合は，空港線の駅の部分が途中に空白セルとして入っているため，
標準的なバス情報フォーマット出力ツールに貼り付けたのちに，不要な部分を削除（あるいは移動）させる。
七隈線については，他路線との乗り入れはないので，縦横を入れ替えたりという面倒な作業は必要ありません。
