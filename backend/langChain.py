from config import settings
import asyncio

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.retrievers import WikipediaRetriever
from langchain.tools import tool

def search_wikipedia(bird: str, max_chars: int = 2000) -> str:
    """Search Wikipedia for information about a single bird species.

    Args:
        bird:      The bird's common name 
        max_chars: How many characters of the article to return.
    """
    retriever = WikipediaRetriever(load_max_docs=1)
    docs = retriever.invoke(bird)

    if not docs:
        return f"No Wikipedia article found for '{bird}'."

    title   = docs[0].metadata.get("title")
    content = docs[0].page_content[:max_chars]
    return f"=== {title} ===\n{content}"


SUMMARY_PROMPT = ChatPromptTemplate.from_template("""
    You are an expert birding guide writing a summary about the {bird_name}. 
    Use ONLY the Wikipedia excerpt below to write a concise summary (maximum 2 sentences per section) for each bird. 
    Do not invent facts not present in the excerpt. 
    
    ─────────────────────────────────
    WIKIPEDIA CONTEXT
    ─────────────────────────────────
    {wikipedia_context}
    ─────────────────────────────────
    
    OBSERVATION DETAILS
    - Latitude:  {latitude}
    - Longitude: {longitude}
    - Date:      {date_info}
    
    First, identify:
    1. The geographic region and country from the coordinates.
    2. The current season for that hemisphere.
    
    Write a structured summary with these sections:
    
    ### [Bird Name]
    
    **Habitat** — Typical environments and geographic range.
    
    **Traits** — Visual appearance (size, plumage, markings) and behaviour (diet,
    nesting, calls, social habits).
    
    **Migration — [Season]** — What is this bird doing right now in this region?
    Is it a resident, seasonal visitor, active migrant, or preparing to depart?
    Name specific wintering or breeding grounds if mentioned in the Wikipedia excerpt.
    """)


async def langchain_classification_summary_agent(
    unique_birds: set,
    job_context_info: list[dict],
) -> dict[str, str]:
    """
    Generate a summary profile of each classified bird using LangChain.

    The LLM uses Wikipedia to fetch information about each bird. 
    It then generates a structured summary for each bird, including habitat, traits, and migration status based on the user's location and date of recording.
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
            wiki_context = search_wikipedia(bird)  
            result = await chain.ainvoke({
                "wikipedia_context": wiki_context,
                "bird_name":         bird,
                "latitude":          ctx["latitude"],
                "longitude":         ctx["longitude"],
                "date_info":         ctx["created_at"],
            })
            return bird, result

    results = await asyncio.gather(*[summarise_one(b) for b in unique_birds])
    return dict(results)

if __name__ == "__main__":
    test_birds = {"Song Sparrow", "House Sparrow"}
    test_context = [{"latitude": 49.2827, "longitude": -123.1207, "created_at": "2026-05-18"}]

    results = asyncio.run(langchain_classification_summary_agent(test_birds, test_context))

    for bird, summary in results.items():
        print(f"\n{'='*60}")
        print(f"  {bird}")
        print('='*60)
        print(summary)