with complaints as (

    select *
    from {{ ref('int_cfpb_complaints_enriched') }}

),

companies as (

    select *
    from {{ ref('dim_company') }}

),

products as (

    select *
    from {{ ref('dim_product') }}

),

issues as (

    select *
    from {{ ref('dim_issue') }}

),

dates as (

    select *
    from {{ ref('dim_date') }}

),

geographies as (

    select *
    from {{ ref('dim_geography') }}

),

submission_channels as (

    select *
    from {{ ref('dim_submission_channel') }}

)

select

    c.complaint_id,

    d.company_key,
    p.product_key,
    i.issue_key,
    dt.date_key as received_date_key,
    g.geography_key,
    sc.submission_channel_key,

    c.state,
    c.zip_code,

    c.submitted_via,

    c.company_response,
    c.company_public_response,

    c.complaint_narrative,
    c.tags,

    c.has_narrative,
    c.narrative_flag,

    c.is_timely_response,
    c.timely_response_flag,
    c.untimely_response_flag,

    c.received_at,
    c.received_date,
    c.received_month,
    c.received_year,
    c.received_month_number,
    c.received_quarter,

    c.sent_to_company_at,
    c.sent_to_company_date,
    c.days_to_send_to_company,

    c.source_file,
    c.ingested_at

from complaints c

left join companies d
    on c.company = d.company_name

left join products p
    on c.product = p.product_name
   and coalesce(c.sub_product, '') =
       coalesce(p.sub_product_name, '')

left join issues i
    on c.issue = i.issue_name
   and coalesce(c.sub_issue, '') =
       coalesce(i.sub_issue_name, '')

left join dates dt
    on c.received_date = dt.calendar_date

left join geographies g
    on coalesce(
        nullif(trim(c.state), ''),
        'UNKNOWN'
    ) = g.state_code

left join submission_channels sc
    on coalesce(
        nullif(trim(c.submitted_via), ''),
        'UNKNOWN'
    ) = sc.submission_channel