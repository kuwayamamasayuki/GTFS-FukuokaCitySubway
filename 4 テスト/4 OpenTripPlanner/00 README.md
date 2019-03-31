OpenTripPlannerによる確認


## テスト概要

OpenTripPlannerを用いて，適当な二点間の時刻や運賃を検索し，その結果を確認する。


## 判定基準

目視で確認し，問題なさそうであれば合格とする。


## テスト詳細

```
cd fcs
java -Xmx1G -jar ./otp-1.3.0-shaded.jar --build . --verbose --inMemory
（「Grizzly Server running.」の表示が出るまでしばらく待って，別ウィンドウで…）
node test001.js
```