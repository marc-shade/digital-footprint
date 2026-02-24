"""Digital Footprint Manager CLI."""

import asyncio
import json
import sys

import click

from digital_footprint.config import get_config
from digital_footprint.db import Database


def _get_db():
    config = get_config()
    db = Database(config)
    db.initialize()
    return db


def _run_async(coro):
    """Run async function from sync CLI context."""
    return asyncio.run(coro)


@click.group()
@click.version_option(version="1.0.0", prog_name="dfp")
def cli():
    """Digital Footprint Manager - Personal data removal and privacy protection."""
    pass


# -- Person commands --

@cli.group()
def person():
    """Manage protected persons."""
    pass


@person.command("add")
@click.argument("name")
@click.option("--email", "-e", multiple=True, help="Email address (repeatable)")
@click.option("--phone", "-p", multiple=True, help="Phone number (repeatable)")
@click.option("--address", "-a", multiple=True, help="Address (repeatable)")
@click.option("--username", "-u", multiple=True, help="Username (repeatable)")
@click.option("--relation", "-r", default="self", help="Relation (self, spouse, child, parent)")
def person_add(name, email, phone, address, username, relation):
    """Add a person to protect."""
    db = _get_db()
    person_id = db.insert_person(
        name=name,
        emails=list(email),
        phones=list(phone),
        addresses=list(address),
        usernames=list(username),
        relation=relation,
    )
    click.echo(f"Added person '{name}' (ID: {person_id})")


@person.command("list")
def person_list():
    """List all protected persons."""
    db = _get_db()
    persons = db.list_persons()
    if not persons:
        click.echo("No persons registered.")
        return
    for p in persons:
        emails = ", ".join(p.emails) if p.emails else "none"
        click.echo(f"  [{p.id}] {p.name} ({p.relation}) - {emails}")


@person.command("show")
@click.argument("person_id", type=int)
def person_show(person_id):
    """Show details for a person."""
    db = _get_db()
    p = db.get_person(person_id)
    if not p:
        click.echo(f"Person {person_id} not found.", err=True)
        sys.exit(1)
    click.echo(f"Name: {p.name}")
    click.echo(f"Relation: {p.relation}")
    click.echo(f"Emails: {', '.join(p.emails) if p.emails else 'none'}")
    click.echo(f"Phones: {', '.join(p.phones) if p.phones else 'none'}")
    click.echo(f"Addresses: {', '.join(p.addresses) if p.addresses else 'none'}")
    click.echo(f"Usernames: {', '.join(p.usernames) if p.usernames else 'none'}")


# -- Scan commands --

@cli.group()
def scan():
    """Run scans (breach, username, dorks)."""
    pass


@scan.command("breach")
@click.argument("email")
def scan_breach(email):
    """Check an email for known data breaches."""
    from digital_footprint.tools.scan_tools import do_breach_check
    config = get_config()
    result = _run_async(do_breach_check(
        email=email,
        hibp_api_key=config.hibp_api_key,
        dehashed_api_key=config.dehashed_api_key,
    ))
    click.echo(result)


@scan.command("username")
@click.argument("username")
@click.option("--timeout", "-t", default=120, help="Timeout in seconds")
def scan_username(username, timeout):
    """Search for a username across 3,000+ sites (Maigret)."""
    from digital_footprint.scanners.username_scanner import search_username

    click.echo(f"Scanning username '{username}' across sites...")
    results = _run_async(search_username(username, timeout=timeout))

    if not results:
        click.echo("No accounts found.")
        return

    click.echo(f"\nFound {len(results)} accounts:\n")
    for r in sorted(results, key=lambda x: x.risk_level, reverse=True):
        marker = {"high": "!!", "medium": "!", "low": "."}[r.risk_level]
        click.echo(f"  [{marker}] {r.site_name}: {r.url}")


@scan.command("dorks")
@click.argument("name")
@click.option("--email", "-e", help="Email to include in dorks")
@click.option("--phone", "-p", help="Phone to include in dorks")
def scan_dorks(name, email, phone):
    """Generate Google dork queries for OSINT."""
    from digital_footprint.scanners.google_dorker import generate_dorks

    dorks = generate_dorks(name=name, email=email, phone=phone)
    click.echo(f"Google Dork Queries for '{name}':\n")
    for i, dork in enumerate(dorks, 1):
        click.echo(f"  {i}. {dork}")


@scan.command("holehe")
@click.argument("email")
def scan_holehe(email):
    """Check which services an email is registered with."""
    from digital_footprint.scanners.holehe_scanner import check_email_registrations

    click.echo(f"Checking email registrations for '{email}'...")
    results = _run_async(check_email_registrations(email))

    if not results:
        click.echo("No registrations found (or holehe not installed).")
        return

    click.echo(f"\nFound {len(results)} registrations:\n")
    for r in results:
        marker = {"high": "!!", "medium": "!", "low": "."}[r.risk_level]
        click.echo(f"  [{marker}] {r.service}")


# -- Broker commands --

@cli.group()
def broker():
    """Manage data broker registry."""
    pass


@broker.command("list")
@click.option("--category", "-c", help="Filter by category")
def broker_list(category):
    """List known data brokers."""
    db = _get_db()
    brokers = db.list_brokers(category=category)
    if not brokers:
        click.echo("No brokers loaded.")
        return
    for b in brokers:
        method = b.opt_out_method or "unknown"
        click.echo(f"  [{b.slug}] {b.name} ({b.category}) - {method}")


@broker.command("stats")
def broker_stats():
    """Show broker registry statistics."""
    db = _get_db()
    stats = db.broker_stats()
    click.echo(json.dumps(stats, indent=2))


# -- Removal commands --

@cli.group()
def remove():
    """Submit and track data removal requests."""
    pass


@remove.command("submit")
@click.argument("person_id", type=int)
@click.argument("broker_slug")
def remove_submit(person_id, broker_slug):
    """Submit a removal request to a broker."""
    from digital_footprint.tools.removal_tools import do_broker_remove
    config = get_config()
    db = _get_db()
    result = do_broker_remove(
        broker_slug=broker_slug,
        person_id=person_id,
        db=db,
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_user=config.smtp_user,
        smtp_password=config.smtp_password,
    )
    click.echo(result)


@remove.command("status")
@click.argument("person_id", type=int)
def remove_status(person_id):
    """Check removal status for a person."""
    from digital_footprint.tools.removal_tools import do_removal_status
    db = _get_db()
    result = do_removal_status(person_id=person_id, db=db)
    click.echo(result)


# -- Pipeline commands --

@cli.command()
@click.argument("person_id", type=int)
def protect(person_id):
    """Run full protection pipeline for a person."""
    from digital_footprint.tools.pipeline_tools import do_protect
    config = get_config()
    db = _get_db()

    click.echo(f"Running protection pipeline for person {person_id}...")
    result = do_protect(person_id=person_id, db=db, config=config)
    click.echo(result)


# -- Status command --

@cli.command()
def status():
    """Show system status dashboard."""
    db = _get_db()
    config = get_config()

    persons = db.list_persons()
    brokers = db.list_brokers()

    click.echo("Digital Footprint Manager - Status")
    click.echo("=" * 40)
    click.echo(f"Persons protected: {len(persons)}")
    click.echo(f"Brokers loaded:    {len(brokers)}")
    click.echo(f"Database:          {config.db_path}")
    click.echo(f"HIBP API key:      {'configured' if config.hibp_api_key else 'not set'}")
    click.echo(f"SMTP:              {'configured' if config.smtp_host else 'not set'}")


def main():
    cli()


if __name__ == "__main__":
    main()
