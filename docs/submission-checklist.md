# Submission Checklist

## Technical links

| Form field | Submission value |
|---|---|
| Deployed Backend API Base URL | `https://document-intelligence-platform-gn7s.onrender.com/api/v1` |
| Deployed Frontend URL | `https://document-intelligence-platform-bice.vercel.app` |
| Deployment Platform Used | `Vercel (frontend), Render (backend and PostgreSQL)` |
| Public GitHub repository | `https://github.com/ryuk7728/document-intelligence-platform` |
| Development approach PPT | `https://docs.google.com/presentation/d/1Ec6sywdyoi3JuIiW2RbvB6bAQoZPVAhkGDm5VCfPlhs/edit?usp=sharing` |

## Verified before submission

- [x] Repository is public.
- [x] Frontend returns HTTP 200 and loads the exact Render API origin.
- [x] Backend health returns HTTP 200 with `database: ok`.
- [x] CORS allows the Vercel origin and does not allow an unrelated origin.
- [x] A real invoice completed OCR, extraction, validation, and persistence through the public API.
- [x] The saved record was retrieved by ID, filename, and history after backend redeployment.
- [x] The final dashboard was visually checked with the persisted record.
- [x] The latest GitHub Actions test and Linux container jobs passed.
- [x] The PPT is uploaded to Google Drive with anyone-with-the-link viewer access and no sign-in required.
- [ ] All personal form fields are completed.
- [x] Every technical submission URL returns HTTP 200 without an authenticated application session.

## Personal form fields still required

- Name
- Email address
- Phone number
- College
- Highest education level
- Highest degree
- Major
- CGPA
- Five-day in-office answer
- Six-month internship/compensation answer
