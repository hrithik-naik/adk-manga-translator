from google.adk.agents import Agent, SequentialAgent, LoopAgent
from google.adk.tools.agent_tool import AgentTool

from .sub_agents.manga_cleaner.agent import manga_cleaner
from .sub_agents.recreator.agent import proof_reader
from .sub_agents.translator.agent import translator
from .tools.tools import get_current_time
refinement_loop = LoopAgent(
    name="PostRefinementLoop",
    max_iterations=1,
    sub_agents=[
        translator,

    ],
    description="Iteratively reviews and refines until the translation meets the requirements",
)
workflow=SequentialAgent(
    name="LinkedInPostGenerationPipeline",
    sub_agents=[
        manga_cleaner,
        refinement_loop,
        proof_reader
    ],
    description="Converts a manga panel from japanese to english input: manga link:<link>",)
root_agent = Agent(
    name="manager",
    model="gemini-2.0-flash",
    description="Manager agent",
    instruction="""
    You are a manager agent that is responsible for overseeing the work of the other agents.

    Always delegate the task to the appropriate agent. Use your best judgement 
    to determine which agent to delegate to.

    You are responsible for delegating tasks to the following agent:
    -manga_cleaner
    """,
    sub_agents=[workflow],
    tools=[
        AgentTool(proof_reader),

    ],

)
