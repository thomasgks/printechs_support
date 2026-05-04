# Google Meet Setup

The Google Meet integration creates a Google Calendar event with `conferenceData.createRequest` and stores the generated Meet link on the Support Ticket.

## Dependencies

Install the Google API libraries in the bench environment:

```bash
bench pip install google-api-python-client google-auth google-auth-oauthlib
```

Restart the bench after installation:

```bash
bench restart
```

## Google Cloud Setup

1. Create or select a Google Cloud project.
2. Enable the Google Calendar API.
3. Create OAuth credentials for a Google account that owns or can write to the target calendar.
4. Generate a refresh token with Calendar event access.

## ERPNext Settings

Open **Printechs Support Google Settings** and set:

- **Enabled**: checked
- **Google Client ID**
- **Google Client Secret**
- **Google Refresh Token**
- **Calendar ID**: `primary` unless using a dedicated calendar
- **Default Meeting Duration**: usually `30`
- **Meeting Title Template**: for example `Support Meeting - {ticket_id}`
- **Auto Email Customer**: checked if customers should be notified immediately

## Usage

On a Support Ticket, click **Google Meet > Enable Google Meet**. The system creates one Meet link per ticket and will not create duplicates. After creation, staff and customers open the meeting in a new browser tab using **Join Google Meet**.
