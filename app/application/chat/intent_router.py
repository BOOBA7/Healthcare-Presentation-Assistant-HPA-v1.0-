from app.application.chat.intent import Intent


class IntentRouter:
    """
    Determines the user's intent from
    a natural language message.
    """

    def route(
        self,
        message: str,
    ) -> Intent:
        """
        Route a user message to the
        appropriate application intent.
        """

        text = message.lower().strip()

        # Greetings

        if any(
            word in text
            for word in [
                "hello",
                "hi",
                "hey",
            ]
        ):
            return Intent.GREETING

        # Help

        if "help" in text:
            return Intent.HELP

        # Presentation

        if (
            "create presentation" in text
            or "new presentation" in text
            or "create a presentation" in text
        ):
            return Intent.CREATE_PRESENTATION

        # Blueprint

        if (
            "generate blueprint" in text
            or "build blueprint" in text
            or "blueprint" == text
        ):
            return Intent.GENERATE_BLUEPRINT

        # Slides

        if "generate slides" in text or "generate slide" in text or "slides" == text:
            return Intent.GENERATE_SLIDES

        if "regenerate slide" in text:
            return Intent.REGENERATE_SLIDE

        # Resources

        if "add resource" in text or "upload" in text:
            return Intent.ADD_RESOURCE

        if "list resources" in text:
            return Intent.LIST_RESOURCES

        # Export

        if "export powerpoint" in text or "export ppt" in text:
            return Intent.EXPORT_POWERPOINT

        if "export pdf" in text:
            return Intent.EXPORT_PDF

        # Workflow

        if "status" in text:
            return Intent.STATUS

        if "reset" in text:
            return Intent.RESET_SESSION

        if "cancel" in text:
            return Intent.CANCEL

        return Intent.UNKNOWN
