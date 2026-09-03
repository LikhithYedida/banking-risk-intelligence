SELECT
    COUNT(*) AS total_rows,

    COUNT(DISTINCT complaint_id)
        AS unique_complaint_ids,

    COUNT(*) - COUNT(DISTINCT complaint_id)
        AS duplicate_complaint_ids,

    COUNT(*) FILTER (
        WHERE complaint_id IS NULL
           OR TRIM(complaint_id) = ''
    ) AS missing_complaint_id,

    COUNT(*) FILTER (
        WHERE product IS NULL
           OR TRIM(product) = ''
    ) AS missing_product,

    COUNT(*) FILTER (
        WHERE issue IS NULL
           OR TRIM(issue) = ''
    ) AS missing_issue,

    COUNT(*) FILTER (
        WHERE company IS NULL
           OR TRIM(company) = ''
    ) AS missing_company,

    COUNT(*) FILTER (
        WHERE date_received IS NULL
           OR TRIM(date_received) = ''
    ) AS missing_date_received,

    COUNT(*) FILTER (
        WHERE timely IS NULL
           OR TRIM(timely) = ''
    ) AS missing_timely,

    COUNT(*) FILTER (
        WHERE timely IS NOT NULL
          AND TRIM(timely) <> ''
          AND timely NOT IN ('Yes', 'No')
    ) AS unexpected_timely_values

FROM raw.cfpb_complaints;