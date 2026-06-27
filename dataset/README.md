# Dataset — Thai Government Lottery results (CE 1990 – 2026)

Source: `https://myhora.com/lottery/stats.aspx?mx=09&vx=40`
Regenerate with: `python3 scraper/scrape_myhora.py`

| File                     | Format | Notes                                   |
| ------------------------ | ------ | --------------------------------------- |
| `lottery_results.csv`    | CSV    | UTF-8, header row                       |
| `lottery_results.sqlite` | SQLite | table `draws`, primary key `DrawDate`   |

- **872 draws**, BE 2533–2569 (CE 1990–2026), through the 16 June 2026 draw.
- Every numeric field is stored as **text** to preserve leading zeros (e.g. `Last2 = "01"`).

## Columns

| Column                  | Meaning (TH)        | Notes                                              |
| ----------------------- | ------------------- | -------------------------------------------------- |
| `DrawDate`              | วันที่ออกรางวัล      | `YYYY-MM-DD`, **Buddhist Era (BE)** calendar       |
| `Year`                  | ปี                  | **Buddhist Era (BE)** year                         |
| `Month`                 | เดือน               | 1–12                                               |
| `FirstPrize`            | รางวัลที่ 1         | usually 6 digits (see note below)                  |
| `Last2`                 | เลขท้าย 2 ตัว (2 ตัวล่าง) |                                               |
| `Front3_1`, `Front3_2`  | เลขหน้า 3 ตัว        | empty before the 1 May 2015 format change          |
| `Back3_1` … `Back3_4`   | เลขท้าย 3 ตัว        | see era note below                                 |

`Back3_3` / `Back3_4` extend the original README schema so no source value is lost.

## Format eras

| Period (CE)   | Front-3 | Back-3 numbers |
| ------------- | ------- | -------------- |
| 1990 – 2015   | none    | **4** (`Back3_1..4`) |
| 2015          | mixed (format changed mid-2015) | mixed |
| 2016 – 2026   | 2 (`Front3_1/2`) | 2 (`Back3_1/2`) |

## Data-quality notes

- **120 draws (concentrated ~1994–1995) have a 7-digit `FirstPrize`.** This is how
  the source publishes them; values are preserved verbatim rather than truncated.
- A few years have fewer than 24 draws (cancelled/rescheduled draws), e.g. CE 2020, 2024.
- `Year`/`DrawDate` use the **Buddhist Era** calendar, matching myhora.com
  (subtract 543 for the Gregorian year — e.g. BE 2569 = CE 2026).
