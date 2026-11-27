# Privacy policy · Corner Shop AI

Last updated: 27 November 2026

Corner Shop AI is an open-source WhatsApp assistant for one small corner shop in Casablanca, built in public by
Oz builds AI. This page explains what it does with your data.

## Who can use it

Only the shop owner and people the owner adds as test recipients. It is not a public service and it does not
message anyone first: it only answers messages sent to it.

## What is stored

When you send a message to the assistant's WhatsApp number, we store:

- the message itself (text, type, time and WhatsApp message id),
- your WhatsApp phone number (to send the answer back),
- what the assistant understood (for example "sale: 3 bread") and the answer it sent.

Images, voice notes and other media are stored only as a message record, not opened or analysed.

## Why

Only to run the shop assistant: understand the owner's sales, deliveries and customer credit, answer back, and
(later) learn the shop's demand to help it avoid running out of stock. No advertising, no profiling, no selling or
sharing of data.

## Where and who

Data is stored in Amazon Web Services in Frankfurt, Germany (eu-central-1), in a private, encrypted database.
Messages are read by an AI model (Claude, through Amazon Bedrock in the EU) only to understand them; they are not
used to train that model. WhatsApp messages travel through Meta's WhatsApp Business Platform, under Meta's own
terms. Nobody else has access.

## How long

Duplicate-check markers are deleted after 7 days. Shop messages are kept while the project runs, and deleted on
request or when the project ends.

## Your choices

You can ask for your data to be deleted at any time: open an issue at
https://github.com/ozmane1/corner-shop-ai/issues (or tell the shop owner) and it will be removed within 30 days.
Stopping is simple: stop messaging the number.

## Changes

Changes to this policy are published in this file, with the git history showing every change.
