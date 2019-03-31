このフォルダには，元データからGTFSデータを作成するためのツールを置いています。

GTFSデータの作成には，主に東京大学空間情報科学研究センター特任教授の西沢明氏による「標準的なバス情報フォーマット出力ツール」（いわゆる「西沢ツール」）を用いています。

ただし，以下の理由などにより、すべてのGTFSデータを標準的なバス情報フォーマット出力ツールにより作成しているわけではありません。

　* GTFSと標準的なバス情報フォーマットにおけるrouteの考え方の違い
  
　* 標準的なバス情報フォーマット出力ツールでは，空港線・箱崎線と七隈線をまたぐ運賃表を作成できないこと（私の使い方がおかしいのかも？）

具体的な修正内容については，「3 標準的なバス情報フォーマット出力ツール（西沢ツール）の出力を修正」フォルダの「00 README.md」を御覧ください。


また，同様の理由により，標準的なバス情報フォーマット出力ツールを一部改造している部分もあります。

具体的な改造内容は以下のとおりです。

* 「a02_9_経路ID内のバス停並びをチェックする」の1417行で「型が一致しません」とエラーになる件
```
RouteSN(RouteNo) & "/運行日＝" & Trim(RouteUnkoubi(RouteNo)) & " 便＝" & Trim(Str(RouteBinNo(RouteNo))) & " <> " & _
```
を
```
RouteSN(RouteNo) & "/運行日＝" & Trim(RouteUnkoubi(RouteNo)) & " 便＝" & Trim(RouteBinNo(RouteNo)) & " <> " & _
```
に変更。1425行も同様。
（VBAの文法上エラーとなる。）


* 「a01_データの不整合や不足をチェックする」内の，109行をコメントアウト

おそらく，標準的なバス情報フォーマットだから必要なチェックであり，GTFSでは必ずしも必要ないチェックであるため。

```
'*** RouteIDのバス停並びをチェックする ***
        Call a02_9_経路ID内のバス停並びをチェックする
```

（参考）[GTFS Data Best Practices](https://gtfs.org/best-practices/#routestxt)「
All trips on a given named route should reference the same route_id.」




* 「a04_7_便情報ファイル出力」内の，1092行～1099行（以下の部分）のコメントアウトを外した。
（なんでコメントアウトされてるんだろう？）

``` 
'            BlockID1 = Trim(Cells(11, C).Value)
'            BlockID2 = Trim(Cells(12, C).Value)
'            BlockID3 = Trim(Cells(13, C).Value)
'            If BlockID3 = "" Then
'              BlockID = ""
'            Else
'              BlockID = BlockID1 & "+" & BlockID2 & "+" & BlockID3
'            End If
```




