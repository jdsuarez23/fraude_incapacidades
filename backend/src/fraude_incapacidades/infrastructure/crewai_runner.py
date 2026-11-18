class CrewAiRunner:
    async def run(self, inputs: dict, task_callback=None):
        from fraude_incapacidades.crew import build_crew

        crew = build_crew(task_callback=task_callback)
        return await crew.kickoff_async(inputs=inputs)
