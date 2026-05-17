# Алгоритмы и правила

## Прогноз сроков

- История выполненных points -> средняя velocity.
- Оценка дней до завершения: `remaining / velocity`.
- Confidence вычисляется через вариативность velocity.

## MAPE

- Метрика качества прогнозов: `mean(abs((actual - predicted) / actual)) * 100`.
- Целевое значение: `< 10%`.

## Автоназначение

Скоринг исполнителя:

- `quality_score`.
- свободная ёмкость (`free_hours_week`).
- совпадение по тегам/навыкам.

## Детекция выгорания

Индикаторы:

- overload ratio (`booked/capacity`).
- доля ночной активности.
- количество context switches.

Результат: `low/medium/high/critical`.

## Риск-оценка

- Risk score = `probability * impact`.
- Автоклассификация в `low..critical`.
- Риск-индекс проекта = среднее по всем рискам.
