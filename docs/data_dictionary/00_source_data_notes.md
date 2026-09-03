# CFPB Consumer Complaint Database - Source Notes

## Dataset Grain
One record represents one consumer complaint.

## Primary Identifier
Complaint ID

## Core Fields
- Date received
- Product
- Sub-product
- Issue
- Sub-issue
- Company
- State
- ZIP code
- Tags
- Submitted via
- Date sent to company
- Company response to consumer
- Timely response?
- Complaint ID

## Initial Data Quality Observations
- Sub-product may be null.
- Sub-issue may be null.
- ZIP code may be partially masked or unavailable.
- Company public response is optional.
- Complaint categories depend on product and issue.

## Source
Consumer Financial Protection Bureau Consumer Complaint Database.