using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using UglyToad.PdfPig;

namespace ProcessCv
{
    class Program
    {
        // Couchbase Settings
        private const string CB_URL = "http://localhost:8093/query/service";
        private const string CB_USER = "Administrator";
        private const string CB_PASSWORD = "password";
        private const string BUCKET_NAME = "hackathon";

        // AI Settings (GitHub Models / OpenAI)
        private const string AI_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions";
        private const string AI_MODEL = "gpt-4o";

        static async Task Main(string[] args)
        {
            if (args.Length < 3)
            {
                Console.WriteLine("Usage: process_cv.exe <pdf_path_or_text> <candidate_id> <api_key>");
                return;
            }

            string inputData = args[0];
            if (!int.TryParse(args[1], out int candidateId))
            {
                Console.WriteLine("Error: candidate_id must be an integer.");
                return;
            }
            string apiKey = args[2];

            try
            {
                // 1. Extract Text
                string rawText;
                if (File.Exists(inputData) && inputData.EndsWith(".pdf", StringComparison.OrdinalIgnoreCase))
                {
                    Console.WriteLine($"Extracting text from PDF: {inputData}...");
                    rawText = ExtractTextFromPdf(inputData);
                }
                else
                {
                    Console.WriteLine("Input detected as raw text string.");
                    rawText = inputData;
                }
                
                // Normalize whitespace
                rawText = Regex.Replace(rawText, @"\s+", " ").Trim();
                
                if (string.IsNullOrWhiteSpace(rawText))
                {
                    Console.WriteLine("Warning: No text extracted from PDF.");
                }
                else 
                {
                     // Debug: Print excerpt
                     Console.WriteLine($"Extracted {rawText.Length} chars. Preview: {rawText.Substring(0, Math.Min(100, rawText.Length))}...");
                }

                // Init HttpClient
                using var client = new HttpClient();
                
                // 2. Fetch Skills
                Console.WriteLine("Fetching ESCO skills from database...");
                var skills = await FetchSkills(client);
                Console.WriteLine($"Loaded {skills.Count} skills.");

                // 3. Match Skills (AI)
                Console.WriteLine("Matching skills using AI...");
                var foundSkills = await MatchSkillsWithAi(client, rawText, skills, apiKey);
                Console.WriteLine($"Found {foundSkills.Count} matching skills.");

                // 4. Update Database
                Console.WriteLine("Updating candidate record...");
                await UpdateCandidate(client, candidateId, rawText, foundSkills);

                Console.WriteLine("Done.");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
                Console.WriteLine(ex.StackTrace);
            }
        }

        static string ExtractTextFromPdf(string path)
        {
            var textBuilder = new StringBuilder();
            using (var pdf = PdfDocument.Open(path))
            {
                foreach (var page in pdf.GetPages())
                {
                    textBuilder.AppendLine(page.Text);
                }
            }
            return textBuilder.ToString();
        }

        static async Task<Dictionary<string, int>> FetchSkills(HttpClient client)
        {
            // Set Basic Auth for Couchbase
            var request = new HttpRequestMessage(HttpMethod.Post, CB_URL);
            var authToken = Convert.ToBase64String(Encoding.ASCII.GetBytes($"{CB_USER}:{CB_PASSWORD}"));
            request.Headers.Authorization = new AuthenticationHeaderValue("Basic", authToken);

            var statement = $"SELECT ID, SkillName FROM `{BUCKET_NAME}`._default.Skill";
            var payload = new { statement = statement };
            request.Content = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");

            var response = await client.SendAsync(request);
            response.EnsureSuccessStatusCode();

            var content = await response.Content.ReadAsStringAsync();
            var doc = JsonDocument.Parse(content);
            var results = doc.RootElement.GetProperty("results");

            var dictionary = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            foreach (var row in results.EnumerateArray())
            {
                string name = row.GetProperty("SkillName").GetString();
                int id = row.GetProperty("ID").GetInt32();
                if (!dictionary.ContainsKey(name))
                {
                    dictionary[name] = id;
                }
            }
            return dictionary;
        }

        static async Task<List<(int Id, string Name)>> MatchSkillsWithAi(HttpClient client, string cvText, Dictionary<string, int> skills, string apiKey)
        {
            // Prepare the prompt
            var skillList = new StringBuilder();
            foreach(var kvp in skills)
            {
                skillList.AppendLine($"{kvp.Value}: {kvp.Key}");
            }

            string systemPrompt = "You are an expert technical recruiter. You will receive a CV and a list of standardized ESCO skills (ID: Name). Your job is to identify which of the standardized skills are present in the CV. Use synonym matching (e.g. 'Python' -> 'Python Programming'). Return ONLY a JSON array of the IDs of the matched skills. Do not return any other text.";
            
            string userPrompt = $@"
AVAILABLE SKILLS:
{skillList}

CV TEXT:
{cvText}

Return JSON Array of IDs:";

            var requestBody = new
            {
                messages = new[]
                {
                    new { role = "system", content = systemPrompt },
                    new { role = "user", content = userPrompt }
                },
                model = AI_MODEL,
                temperature = 0.1 // Low temperature for deterministic results
            };

            // Send to AI
            var request = new HttpRequestMessage(HttpMethod.Post, AI_ENDPOINT);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
            request.Content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");

            var response = await client.SendAsync(request);
            if (!response.IsSuccessStatusCode)
            {
                string err = await response.Content.ReadAsStringAsync();
                throw new Exception($"AI Request Failed: {response.StatusCode} - {err}");
            }

            var responseContent = await response.Content.ReadAsStringAsync();
            var jsonDoc = JsonDocument.Parse(responseContent);
            
            // Extract the content string
            string aiContent = jsonDoc.RootElement
                .GetProperty("choices")[0]
                .GetProperty("message")
                .GetProperty("content")
                .GetString();

            // Parse the JSON array IDs from the AI response
            // Clean up potential markdown code blocks ```json ... ```
            aiContent = aiContent.Replace("```json", "").Replace("```", "").Trim();

            var matches = new List<(int, string)>();
            try 
            {
                var ids = JsonSerializer.Deserialize<int[]>(aiContent);
                
                // Reconstruct the result list
                // Reverse lookup map
                var idToName = new Dictionary<int, string>();
                foreach(var k in skills) idToName[k.Value] = k.Key;

                foreach(int id in ids)
                {
                    if(idToName.ContainsKey(id))
                    {
                        matches.Add((id, idToName[id]));
                    }
                }
            }
            catch(Exception e)
            {
                Console.WriteLine($"Failed to parse AI response: {aiContent}");
                throw e;
            }

            return matches;
        }

        static async Task UpdateCandidate(HttpClient client, int candidateId, string cvText, List<(int Id, string Name)> foundSkills)
        {
            // Request Helper for Couchbase
             async Task<HttpResponseMessage> SendQuery(object body)
             {
                var req = new HttpRequestMessage(HttpMethod.Post, CB_URL);
                var authToken = Convert.ToBase64String(Encoding.ASCII.GetBytes($"{CB_USER}:{CB_PASSWORD}"));
                req.Headers.Authorization = new AuthenticationHeaderValue("Basic", authToken);
                req.Content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
                return await client.SendAsync(req);
             }

            // Update 1: Set CVText
            var updateData = new Dictionary<string, object>();
            updateData["statement"] = $"UPDATE `{BUCKET_NAME}`._default.Candidate SET CVText = $cvText WHERE ID = $cId";
            updateData["$cvText"] = cvText;
            updateData["$cId"] = candidateId;

            var resUpdate = await SendQuery(updateData);
            if (!resUpdate.IsSuccessStatusCode)
            {
                Console.WriteLine($"Error updating CVText: {await resUpdate.Content.ReadAsStringAsync()}");
            }
            else 
            {
                Console.WriteLine("CVText updated.");
            }

            // Update 2: Upsert Skills
            foreach (var skill in foundSkills)
            {
                 string key = $"candidateskill::{candidateId}::{skill.Id}";
                 
                 var upsertData = new Dictionary<string, object>();
                 upsertData["statement"] = $"UPSERT INTO `{BUCKET_NAME}`._default.CandidateSkill (KEY, VALUE) VALUES ($key, {{ \"CandidateID\": $cId, \"SkillID\": $sId, \"Level\": 1 }})";
                 upsertData["$key"] = key;
                 upsertData["$cId"] = candidateId;
                 upsertData["$sId"] = skill.Id;

                 var resSkill = await SendQuery(upsertData);
                 if (resSkill.IsSuccessStatusCode)
                 {
                     Console.WriteLine($"Linked Skill: {skill.Name}");
                 }
                 else
                 {
                     Console.WriteLine($"Failed to link skill {skill.Name}: {await resSkill.Content.ReadAsStringAsync()}");
                 }
            }
        }
    }
}
