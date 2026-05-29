## How Science Is Used

A ciencia do V1 vem do registry aprovado em `data/knowledge/science_refs.yaml`. Esse arquivo e a fonte canonica. `data/processed/science_refs.csv` e derivado do YAML e nao deve ser editado manualmente.

O sistema nao usa ciencia como autoridade generica para forcar treino. Cada referencia aprovada tem:

- `science_ref_id`
- DOI ou URL
- populacao estudada
- achado principal
- aplicacao pratica
- limites
- tags

Na pratica, uma regra de treino so deve citar fontes do registry. Quando a evidencia individual de Matheus ou Bruna conflita com a direcao geral da literatura, a decisao deve favorecer seguranca e contexto individual.

## Approved Registry

Referencias aprovadas no V1:

- `safety-red-flag-conservative`: consenso ECSS/ACSM sobre overtraining e red flags; usado para falhar fechado com fadiga persistente, sintomas, sono ruim e sinais de risco.
- `load-management-recovery`: consenso IOC sobre carga no esporte e risco de lesao; usado para evitar aumentos bruscos, empilhamento de carga e compensacao.
- `achilles-tendinopathy-load`: estudo com modelo de monitoramento de dor em tendinopatia de Aquiles; usado para governar a participacao de Matheus por sintomas.
- `sleep-fatigue-load-management`: revisao sobre sono, performance e recuperacao; usado para reduzir carga quando sono ruim aparece junto de fadiga ou esforco forte.
- `volleyball-neuromuscular-load`: revisao sobre estresse, fadiga neuromuscular e bem-estar no volei; usado para contar volei como sinal de carga, sem fingir que quantifica risco de corrida no dia seguinte.
- `training-consistency-principle`: posicao ACSM sobre quantidade e qualidade de exercicio; usado como suporte geral para consistencia e exercicio regular.
- `seiler-intensity-distribution`: estudo de distribuicao de intensidade em atletas de endurance; usado para manter a maior parte dos treinos faceis e evitar transformar longao em threshold.
- `threshold-training-lactate`: meta-analise sobre limiares lactato/ventilatorio; usado para justificar threshold/cruise intervals como estimulo valido, mas limitado.
- `strength-running-economy`: meta-analise sobre treino de forca e economia de corrida; usado para manter forca como suporte, ajustando por recuperacao.

## Practical Interpretation

Mapeamento para decisoes de Matheus e Bruna:

- Consistencia: manter tres corridas semanais quando a recuperacao permite, sem adicionar volume para compensar falhas.
- Easy/long run: longao deve ficar leve para preservar base aerobica e reduzir risco de excesso de intensidade.
- Threshold/cruise intervals: usar como qualidade controlada para Bruna, principalmente em faixas sustentaveis, nao como all-out.
- VO2/velocidade: V1 nao prioriza tiros maximos; a velocidade residual de Matheus e um risco se virar foco.
- Carga aguda/cronica: aumentar volume e intensidade separadamente, com descarga quando fadiga acumula.
- Aquiles: qualquer piora em Matheus altera o treino antes de virar lesao.
- Volei: quarta-feira conta como carga neuromuscular; quinta deve evitar maximo quando Bruna relata cansaco.
- Forca: academia ajuda, mas perna pesada muda o treino de corrida.
- Sono: sono ruim reduz confianca e pode reduzir volume/intensidade.
- Provas: prova all-out gera 2-4 dias de recuperacao e nao deve ser seguida por qualidade precoce.

Regras conservadoras atuais:

- `bruna_pse >= 9`: proximo treino leve, reduzido ou off.
- Sintomas fortes: reduzir intensidade.
- `matheus_achilles_morning` ou `matheus_achilles_after` acima de 3: remover velocidade/descidas/tiros.
- Aquiles acima de 5: Matheus nao deve ser pacer de treino exigente.
- Volei no dia anterior ou sono ruim: reduzir ambicao do treino.
- Check-in ausente: recomendacao de baixa confianca ou resolucao manual.

## Limits

O V1 nao diagnostica lesao, overtraining, condicao cardiaca, anemia, disturbio de sono ou qualquer condicao medica. Sintomas fortes, dor persistente, visao embacada recorrente, dor no peito, tontura, falta de ar anormal ou piora do Aquiles exigem avaliacao profissional.

Limites especificos:

- A literatura do registry orienta principios, nao prediz a resposta individual treino a treino.
- A fonte de volei apoia monitoramento de carga e fadiga, mas nao quantifica risco exato de corrida no dia seguinte.
- A fonte de Seiler e descritiva e em esquiadores competitivos; ela nao vira dogma rigido de 80/20.
- A fonte de threshold cobre populacoes e protocolos variados; pace ainda precisa de calibracao por prova, PSE e contexto.
- Garmin do Matheus nao mede Bruna.
- HR manual de Bruna so entra quando fornecida com evidencia.
- Dashboard e relatorios sao auxiliares de decisao; o contrato de seguranca prevalece.
