"""
Certinator AI — Delete Foundry Agents Utility

Interactive CLI script to list and delete agents (v2) created in
Azure AI Foundry. Uses the Azure AI Projects SDK (AgentsOperations).

Usage:
    python -m utils.delete_foundry_agents
"""

from __future__ import annotations

import os
import sys

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


def get_project_client() -> AIProjectClient:
    """
    Create and return an AIProjectClient using DefaultAzureCredential.

    Returns:
        AIProjectClient: Authenticated client for Azure AI Foundry.

    Raises:
        SystemExit: If FOUNDRY_PROJECT_ENDPOINT is not configured.
    """
    endpoint = os.getenv("LLM_ENDPOINT", "")
    if not endpoint:
        print("Error: LLM_ENDPOINT is not set in .env")
        sys.exit(1)

    credential = DefaultAzureCredential()
    return AIProjectClient(endpoint=endpoint, credential=credential)


def list_agents(client: AIProjectClient) -> list:
    """
    Retrieve all agents (v2) from the Foundry project.

    Parameters:
        client (AIProjectClient): Authenticated project client.

    Returns:
        list: List of agent objects from the project.
    """
    agents = []
    for agent in client.agents.list():
        agents.append(agent)
    return agents


def display_agents(agents: list) -> None:
    """
    Display a formatted table of agents with index numbers.

    Parameters:
        agents (list): List of agent objects to display.
    """
    if not agents:
        print("\nNo agents found in the project.")
        return

    print("\n" + "=" * 80)
    print("AGENTS IN FOUNDRY PROJECT (v2)")
    print("=" * 80)
    print(f"{'#':<4} {'Name':<40} {'Kind':<20} {'Description':<30}")
    print("-" * 100)

    for idx, agent in enumerate(agents, start=1):
        agent_name = agent.get("name", "Unnamed")
        agent_kind = agent.get("kind", "N/A")
        agent_desc = agent.get("description", "") or ""
        # Truncate description if too long
        if len(agent_desc) > 27:
            agent_desc = agent_desc[:27] + "..."
        print(f"{idx:<4} {agent_name:<40} {agent_kind:<20} {agent_desc:<30}")

    print("-" * 100)
    print(f"Total: {len(agents)} agent(s)")
    print()


def get_deletion_selection(agents: list) -> list:
    """
    Prompt user to select which agents to delete.

    Parameters:
        agents (list): List of agent objects.

    Returns:
        list: List of selected agent objects to delete.

    Note:
        User can enter:
        - 'all' to select all agents
        - Comma-separated numbers (e.g., '1,2,3')
        - Single number
        - 'q' or empty to cancel
    """
    print("Select agents to delete:")
    print("  - Enter agent numbers (e.g., '1,2,3' or '1-5')")
    print("  - Enter 'all' to delete all agents")
    print("  - Enter 'q' or press Enter to cancel")
    print()

    selection = input("Your selection: ").strip().lower()

    if not selection or selection == "q":
        return []

    if selection == "all":
        return agents.copy()

    selected_agents = []
    try:
        # Handle comma-separated values and ranges
        parts = selection.replace(" ", "").split(",")
        indices = set()

        for part in parts:
            if "-" in part:
                # Handle range (e.g., '1-5')
                start, end = part.split("-")
                for i in range(int(start), int(end) + 1):
                    indices.add(i)
            else:
                indices.add(int(part))

        for idx in sorted(indices):
            if 1 <= idx <= len(agents):
                selected_agents.append(agents[idx - 1])
            else:
                print(f"Warning: Index {idx} is out of range, skipping.")

    except ValueError:
        print("Error: Invalid input. Please enter numbers or 'all'.")
        return []

    return selected_agents


def confirm_deletion(agents_to_delete: list) -> bool:
    """
    Ask user to confirm the deletion of selected agents.

    Parameters:
        agents_to_delete (list): List of agents selected for deletion.

    Returns:
        bool: True if user confirms, False otherwise.
    """
    if not agents_to_delete:
        return False

    print("\n" + "=" * 80)
    print("AGENTS SELECTED FOR DELETION")
    print("=" * 80)

    for agent in agents_to_delete:
        agent_name = agent.get("name", "Unnamed")
        agent_kind = agent.get("kind", "N/A")
        print(f"  - {agent_name} ({agent_kind})")

    print()
    print(f"WARNING: You are about to delete {len(agents_to_delete)} agent(s).")
    print("This action cannot be undone!")
    print()

    confirmation = input("Type 'DELETE' to confirm: ").strip()
    return confirmation == "DELETE"


def delete_agents(client: AIProjectClient, agents_to_delete: list) -> None:
    """
    Delete the specified agents from the Foundry project.

    Parameters:
        client (AIProjectClient): Authenticated project client.
        agents_to_delete (list): List of agents to delete.
    """
    print("\nDeleting agents...")
    deleted_count = 0
    failed_count = 0

    for agent in agents_to_delete:
        agent_name = agent.get("name", None)

        if not agent_name:
            print("  [SKIP] Agent has no name")
            continue

        try:
            client.agents.delete(agent_name)
            print(f"  [OK] Deleted: {agent_name}")
            deleted_count += 1
        except Exception as e:
            print(f"  [FAIL] {agent_name}: {e}")
            failed_count += 1

    print()
    print(f"Summary: {deleted_count} deleted, {failed_count} failed")


def main() -> None:
    """
    Main entry point for the agent deletion utility.

    Workflow:
        1. Load environment variables
        2. Connect to Foundry project
        3. List all agents
        4. Prompt user for selection
        5. Confirm and delete selected agents
    """
    # Load environment variables from .env file
    load_dotenv()

    print("\n" + "=" * 80)
    print("CERTINATOR AI — FOUNDRY AGENT CLEANUP UTILITY")
    print("=" * 80)

    # Connect to Foundry project
    print("\nConnecting to Azure AI Foundry...")
    try:
        client = get_project_client()
        print("Connected successfully!")
    except Exception as e:
        print(f"Error connecting to Foundry: {e}")
        sys.exit(1)

    # List all agents
    print("\nFetching agents from project...")
    try:
        agents = list_agents(client)
    except Exception as e:
        print(f"Error fetching agents: {e}")
        sys.exit(1)

    # Display agents
    display_agents(agents)

    if not agents:
        print("Nothing to delete. Exiting.")
        sys.exit(0)

    # Get user selection
    agents_to_delete = get_deletion_selection(agents)

    if not agents_to_delete:
        print("\nNo agents selected. Exiting.")
        sys.exit(0)

    # Confirm and delete
    if confirm_deletion(agents_to_delete):
        delete_agents(client, agents_to_delete)
        print("\nDone!")
    else:
        print("\nDeletion cancelled.")


if __name__ == "__main__":
    main()
