import os

from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import (
	SerperDevTool,
	DallETool
)
from single_instagram_post_creator.tools.zapier_instagram_webhook import ZapierInstagramWebhookTool




@CrewBase
class SingleInstagramPostCreatorCrew:
    """SingleInstagramPostCreator crew"""

    
    @agent
    def social_media_content_strategist(self) -> Agent:
        
        return Agent(
            config=self.agents_config["social_media_content_strategist"],
            
            
            tools=[				SerperDevTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.7,
            ),
            
        )
    
    @agent
    def content_publishing_manager(self) -> Agent:
        
        return Agent(
            config=self.agents_config["content_publishing_manager"],
            
            
            tools=[				ZapierInstagramWebhookTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.7,
            ),
            
        )
    
    @agent
    def visual_content_creator(self) -> Agent:
        
        return Agent(
            config=self.agents_config["visual_content_creator"],
            
            
            tools=[				DallETool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.7,
            ),
            
        )
    

    
    @task
    def generate_single_post_content_idea(self) -> Task:
        return Task(
            config=self.tasks_config["generate_single_post_content_idea"],
            markdown=False,
            
            
        )
    
    @task
    def create_single_instagram_image(self) -> Task:
        return Task(
            config=self.tasks_config["create_single_instagram_image"],
            markdown=False,
            
            
        )
    
    @task
    def send_content_to_zapier_webhook(self) -> Task:
        return Task(
            config=self.tasks_config["send_content_to_zapier_webhook"],
            markdown=False,
            
            
        )
    

    @crew
    def crew(self) -> Crew:
        """Creates the SingleInstagramPostCreator crew"""
        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )

    def _load_response_format(self, name):
        with open(os.path.join(self.base_directory, "config", f"{name}.json")) as f:
            json_schema = json.loads(f.read())

        return SchemaConverter.build(json_schema)
