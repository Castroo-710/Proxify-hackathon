# CV Processor (C#)

A standalone tool to parse resumes (PDF), match them against ESCO skills using AI (OpenAI/GitHub Models), and update a Couchbase database.

## Prerequisites

1.  **Docker** (running the Couchbase container)
2.  **.NET 9.0 SDK**
3.  **GitHub/OpenAI API Key**

## Setup

1.  Navigate to the project directory:
    ```bash
    cd process_cv_csharp
    ```

2.  Restore dependencies:
    ```bash
    dotnet restore
    ```

## Usage

Run the tool using `dotnet run`. You need to provide 3 arguments:
1.  Path to the PDF file.
2.  Candidate ID (integer) to update in the database.
3.  Your AI API Key.

```bash
dotnet run --project process_cv_csharp -- "path/to/resume.pdf" <CANDIDATE_ID> "<API_KEY>"
```

### Example

```bash
dotnet run --project process_cv_csharp -- "C:\Users\Malin\Downloads\cv_software_developer_junior.pdf" 1 "github_pat_..."
```

## How it Works

1.  **Extracts Text:** Uses `PdfPig` to read raw text from the PDF.
2.  **Fetches Skills:** Pulls the list of valid ESCO skills from Couchbase (`hackathon` bucket).
3.  **AI Matching:** Sends the Resume + Skills list to `gpt-4o`. The AI identifies matches (fuzzy matching) and returns IDs.
4.  **Updates Database:**
    *   Updates the `Candidate` document with the full `CVText`.
    *   Inserts `CandidateSkill` records for every matched skill.
