"""Unified data model for aircraft register lookups."""

from dataclasses import dataclass, field, asdict


@dataclass
class RegisterData:
    """Data returned by any country register lookup."""

    registration: str
    manufacturer: str | None = None
    aircraft_type: str | None = None
    serial_number: str | None = None
    year_built: int | None = None
    owner: str | None = None
    mtow: str | None = None
    engine: str | None = None
    military_serial: str | None = None
    total_hours: str | None = None
    ownership_timeline: list[dict] = field(default_factory=list)
    register_url: str | None = None

    def to_prompt_context(self) -> str:
        """Format register data as text for the Claude narrative prompt."""
        lines = [f"Official register data for {self.registration}:"]
        if self.manufacturer:
            lines.append(f"Manufacturer: {self.manufacturer}")
        if self.aircraft_type:
            lines.append(f"Type: {self.aircraft_type}")
        if self.serial_number:
            lines.append(f"Serial number: {self.serial_number}")
        if self.military_serial:
            lines.append(f"Previous/Military ID: {self.military_serial}")
        if self.year_built:
            lines.append(f"Year built: {self.year_built}")
        if self.owner:
            lines.append(f"Registered owner: {self.owner}")
        if self.mtow:
            lines.append(f"MTOW: {self.mtow}")
        if self.engine:
            lines.append(f"Engine: {self.engine}")
        if self.total_hours:
            lines.append(f"Total airframe hours: {self.total_hours}")
        if self.ownership_timeline:
            lines.append("\nOwnership history (most recent first):")
            for entry in self.ownership_timeline:
                owner = entry.get("owner", "Unknown")
                from_d = entry.get("from_display", "?")
                to_d = entry.get("to_display", "present")
                line = f"  {from_d} to {to_d}: {owner}"
                notes = entry.get("notes", "")
                if notes:
                    line += f" ({notes})"
                lines.append(line)
        return "\n".join(lines)

    def to_cache_dict(self) -> dict:
        """Serialise for DB register_data JSONB column."""
        return {
            "ownership_timeline": self.ownership_timeline,
            "manufacturer": self.manufacturer,
            "year_built": self.year_built,
            "serial_number": self.serial_number,
            "military_serial": self.military_serial,
            "total_hours": self.total_hours,
            "engine": self.engine,
            "mtow": self.mtow,
            "register_url": self.register_url,
        }
