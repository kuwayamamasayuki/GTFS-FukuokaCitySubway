このフォルダにある「運賃表作成.xlsm」は，fare_attributes.txt及びfare_rules.txtを作成するためのExcelファイルです。

Excelファイル内の表１に各区の金額を入力すると，表２に反映されます。
その後，右下の「fare_rules.txt等作成」ボタンをクリックすると，fare_attributes.txt及びfare_rules.txtファイルが作成されます。



fare_attributes.txtはこんな書き方が必要なのかと思われるかもしれませんが，[googletransitdatafeed - FareExamples.wiki](https://code.google.com/archive/p/googletransitdatafeed/wikis/FareExamples.wiki)
の，Excample 6: Fare depends on station pairs, how you get there doesn't matterに記載の方法に則って，fare_attributes.txt及びfare_rules.txtを生成しています。


また，プログラムの前提条件として，stops.txtで定義されるstop_idがその駅のzone_idと等しい数字だという前提としていますので，この前提を崩す場合には，プログラムの改修が必要です。



