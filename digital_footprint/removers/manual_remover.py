"""Manual removal instruction generator for phone/mail opt-outs."""

from datetime import datetime


class ManualRemover:
    def submit(self, person: dict, broker: dict) -> dict:
        opt_out = broker.get("opt_out", {})
        method = opt_out.get("method", "unknown")
        steps = opt_out.get("steps", [])
        broker_name = broker.get("name", "Unknown Broker")

        lines = [
            f"Removal Instructions for {broker_name}",
            f"{'=' * (len(broker_name) + 28)}",
            "",
            f"Method: {method.upper()}",
        ]

        if method == "phone" and opt_out.get("phone"):
            lines.append(f"Phone: {opt_out['phone']}")
        if method == "mail" and opt_out.get("mail_address"):
            lines.append(f"Mail to: {opt_out['mail_address']}")

        lines.append("")
        lines.append("Your information to reference:")
        lines.append(f"  Name: {person.get('name', '')}")
        lines.append(f"  Email: {person.get('email', '')}")
        if person.get("phone"):
            lines.append(f"  Phone: {person['phone']}")
        if person.get("address"):
            lines.append(f"  Address: {person['address']}")

        lines.append("")
        if steps:
            lines.append("Steps:")
            for i, step in enumerate(steps, 1):
                lines.append(f"  {i}. {step}")
        else:
            lines.append(f"Contact {broker_name} using the method above and request removal of your personal data.")

        instructions = "\n".join(lines)

        return {
            "status": "instructions_generated",
            "method": method,
            "broker": broker_name,
            "instructions": instructions,
            "generated_at": datetime.now().isoformat(),
        }
