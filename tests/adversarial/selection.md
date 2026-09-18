# 変更候補の選択（source 編集前）

評価基準: impact × frequency × confidence を各1–5で評定。frequencyは実利用ログからの頻度ではなく、この固定adversarial corpusと契約上の到達可能性に対するレビュー判断。積は優先順位の補助で、実測効果や客観的優先度ではない。

| ID | failure mode / realistic scenario | 現行の場所 | I×F×C | 最小変更 | observable prediction / fixture |
|---|---|---|---|---|---|
| C1 | 不可逆2条件migrationを落とし、3条件既知UIには入口が競合 | SKILL Trigger Guidance、description、input契約 | 4×5×5=100 | 固定countを残余不確実性のlate-discovery costと削減可能性に置換、部分成果物はdomain ownerへ | R09–14/R37 heavy、R01–04 coding、裸の自然文はclarify |
| C2 | bare/default AUTORUN_FULLの無入力をlaunch・product委任と読む | SKILL Modes/P0 boundary | 5×4×5=100 | modeとgrantを分離。goalまたは明示選択委任・scope・予算の既存grantを一度照合。60秒規則削除 | authorization-01–12、R73–78。権限充足済みrunに重複承認なし |
| C3 | 一つの弱いticket→多数persona→synthetic reaction一致を需要証拠へ変換 | P0 scoring、P1 count/anchor、P5 reaction | 5×5×5=125 | claim単位の出所・支持範囲・重複sourceを明記。syntheticは仮説、数を義務化しない。missing scoreは未測定 | demand-01–20。独立source一つは一つ、定性/unmeasurableと実験を許容 |
| C4 | 元要求の欠落、AC分割/demotionで高conformance、誤specをP6で修理 | P4/VERIFY percent、AC-only入力、all-fail-P6 | 5×4×5=100 | original obligation・decision-critical coverageをgate本体にしpercentはsummary。原intent/oracle出所を読み、最初の誤決定ownerへ返す | acceptance-01–30、independence-01–20、return-01–24。同engine/context/evidence/oracleを区別 |
| C5 | 高リスク統合証拠unavailableやrollback impossible理由だけでreadiness判定 | P5→VERIFY integration、Ship enum gate | 5×3×5=75 | 既存P5でrisk-specific必要証拠を明記、既存VERIFY/Shipで未充足block。impossibleには実証controlsと明示risk acceptance | acceptance-14–18/29–30、rollback-01–10。low-risk E3独立の既存床は維持 |

全5件とも現在の `tools/lint.py` が読むのはfrontmatter・構造・パス・サイズであり、意味の真偽、grant、coverage、証拠の独立性を検査しない。既存20 mutation + clean-tree selftestはその静的契約のみを検証する。新たに意味保証のふりをするlintルールは追加しない。fixtureは契約のadversarial review材料・外部runnerへの評価入力であり、文書編集だけでagentの実行成功を証明しない。

## 比較したが今回選ばない候補

| 候補 | I×F×C | 理由 |
|---|---|---|
| phaseごとsealed recordの縮小 | 2×5×5=50 | real runのrecord diffがなく、schema全体変更は5件の外。入口で不必要runを防ぐ方が小さい |
| resume freshness binding | 5×2×5=50 | checkpointをfreshness proofとする危険は残る。host/git/artifact依存schemaを別変更にし、今回は全体再設計しない |
| specialist fallback等価性 | 5×2×4=40 | 同じgate≠同じquality。能力欠落の独立評価が必要で、今回のscopeへ隠して追加しない |
| RPNのordinal積と閾値 | 5×2×4=40 | concrete hazardが本体という評価はするが、既存risk語彙の全置換は別変更 |
| engine名固定cap/能力claim | 3×4×3=36 | 現在の性能比較データなし。benchmark systemを足すことは改善根拠にならない |
| remaining-cost budget policy | 4×3×3=36 | 有用だがruntime計測/enforcementを今回新設しない。hard ceilingとgrantは維持 |
| P2強制二案 | 3×2×5=30 | 6ケースで人工的alternativeを確認。1 feasible evidence escapeは妥当だが今回は最大5件を超えない |

予測は `predictions.md` に固定済み。変更後の結果は別ファイルへ記録し、失敗に合わせて予測や80ケースを書き換えない。
