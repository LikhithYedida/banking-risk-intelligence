with issues as (

    select distinct

        issue,
        sub_issue

    from {{ ref('int_cfpb_complaints_enriched') }}

    where issue is not null

)

select

    md5(
        lower(
            trim(issue)
            || '|'
            || coalesce(trim(sub_issue), '')
        )
    ) as issue_key,

    issue as issue_name,

    sub_issue as sub_issue_name

from issues