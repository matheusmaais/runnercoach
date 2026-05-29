# LLM Running Coach Recommendation

- Recommendation ID: rec-20260528-race-strategy-10k-polish-w1
- Action: reduce_next_workout
- Decision type: race_strategy
- Confidence: medium
- Science refs: volleyball-neuromuscular-load, load-management-recovery, threshold-training-lactate, sleep-fatigue-load-management, training-consistency-principle

## Summary

Treino compartilhado de 28/05 (7.47km a 6:47/km, PSE 7, sem sintomas) confirma Bruna operacional para a prova diagnóstica de 10k em 31/05, mas a carga de vôlei na quarta-feira e o sono regular exigem estratégia conservadora de largada. Guardrail ativo reduz a prescrição: não arriscar ritmo acima do limiar estimado (6:00/km) sem check-in confirmando recuperação completa na manhã da prova. Matheus deve condicionar participação ao sinal do Aquiles em 31/05 pela manhã.

## What The Workout Showed

O treino compartilhado de 28/05 (shared_run=true, bruna_present=true) a 6:47/km com PSE 7 e ausência de sintomas indica que Bruna completou carga operacional moderada um dia após vôlei com sono regular, sem sinais de sobrecarga aguda. O ritmo está dentro da faixa easy/long run estimada (6:40-7:00/km), confirmando que o esforço foi aeróbico controlado. A ausência de dados de FC de Bruna impede confirmação da intensidade fisiológica real. O segmento solo de Matheus (1.33km a 4:22/km) é Matheus-only e não é usado como evidência de evolução de Bruna. Aquiles de Matheus zerado após o treino é sinal positivo para continuidade.

## Risk Assessment

Risco moderado para a prova diagnóstica de 10k em 31/05. Fatores de risco ativos: (1) vôlei na quarta-feira gera carga neuromuscular residual que pode afetar recrutamento muscular e percepção de esforço na prova; (2) qualidade de sono reportada como 'regular' no treino de 28/05, sem confirmação de recuperação adequada até 31/05; (3) 19 check-ins ausentes limitam a confiança no estado de fadiga acumulada de Bruna; (4) Aquiles de Matheus zerado em 28/05 é positivo, mas sem check-in da manhã de 31/05 não é possível confirmar prontidão para esforço de prova. Guardrail determinístico ativo: volleyball_previous_day aciona reduce_next_workout. Sem sintomas ativos de Bruna e PSE 7/10 em 7.47km a 6:47/km indicam carga gerenciável, mas não confirmam prontidão para esforço máximo de prova.

## Next Workout

2026-05-31 diagnostic_race_10k: Bruna deve correr o 10k com estratégia conservadora no primeiro km, mantendo ritmo entre 6:10-6:20/km nos primeiros 5km e ajustando conforme percepção de esforço. Não tentar bater pace de prova rústica (5:50/km) como ritmo sustentado. Matheus deve gerenciar esforço conforme sinal do Aquiles na manhã da prova; se Aquiles > 0 na manhã, reduzir intensidade ou substituir por corrida fácil. Ambos devem reportar check-in na manhã de 31/05 antes de qualquer decisão final.
