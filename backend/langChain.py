import wikipedia
from config import settings
import asyncio

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.retrievers import WikipediaRetriever
from langchain.tools import tool

wikipedia.set_user_agent(settings.WIKIPEDIA_USER_AGENT)


async def search_wikipedia(bird: str, max_chars: int = 2000) -> str:
    """Search Wikipedia for information about a single bird species.

    Args:
        bird:      The bird's common name
        max_chars: How many characters of the article to return.
    """
    retriever = WikipediaRetriever(load_max_docs=1)

    try:
        docs = await retriever.ainvoke(bird)
    except Exception as e:
        return f"Error fetching Wikipedia context for '{bird}': {e}"

    if not docs:
        return f"No Wikipedia article found for '{bird}'."

    title = docs[0].metadata.get("title")
    content = docs[0].page_content[:max_chars]
    return f"=== {title} ===\n{content}"


SUMMARY_PROMPT = ChatPromptTemplate.from_template("""
    You are an expert birding guide writing a polished, user-facing summary about the {bird_name}. 
    Use ONLY the provided context to write a concise summary (maximum 2 sentences per section).
    
    CRITICAL RULES:
    1. NO META-TALK: Never mention "Wikipedia", "the excerpt", the exact date, or the coordinates. 
    Write as if you simply know these facts.
    2. MISSING DATA: If the context lacks specific migration details for this region/season, 
    just state its general migratory habits smoothly. Do not apologize or state that information is missing.
    
    ─────────────────────────────────
    BACKGROUND CONTEXT
    ─────────────────────────────────
    {wikipedia_context}
    ─────────────────────────────────
    
    OBSERVATION DETAILS (Use silently to determine the season and location):
    - Latitude:  {latitude}
    - Longitude: {longitude}
    - Date:      {date_info}
    
    Write a structured summary with EXACTLY these sections:
    
    ### {bird_name}
    
    **Habitat** — Typical environments and geographic range.
    
    **Traits** — Visual appearance (size, plumage, markings) and behaviour (diet, nesting, calls).
    
    **Activity — [Insert Season Here]** — What is this bird doing right now in this season?
    """)


async def langchain_classification_summary(
    unique_birds: set,
    job_context_info: list[dict],
) -> dict[str, str]:
    """
    Generate a summary profile of each classified bird using LangChain.

    The LLM uses Wikipedia to fetch information about each bird.
    It then generates a structured summary for each bird, including habitat, traits, and activity based on the user's location and date of recording.
    """

    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=settings.GROQ_API_KEY,
        temperature=0,
    )

    chain = SUMMARY_PROMPT | llm | StrOutputParser()
    ctx = job_context_info[0]

    # cap at 3 concurrent calls to stay within grok free tier
    semaphore = asyncio.Semaphore(3)

    # run all birds concurrently
    async def summarise_one(bird: str) -> tuple[str, str]:
        async with semaphore:
            wiki_context = await search_wikipedia(bird)

            result = await chain.ainvoke(
                {
                    "wikipedia_context": wiki_context,
                    "bird_name": bird,
                    "latitude": ctx["latitude"],
                    "longitude": ctx["longitude"],
                    "date_info": ctx["created_at"],
                }
            )
            return bird, result

    try:
        results = await asyncio.gather(*[summarise_one(b) for b in unique_birds])
        return dict(results)
    except Exception as e:
        return {"error": f"Error generating LangChain summary: {e}"}