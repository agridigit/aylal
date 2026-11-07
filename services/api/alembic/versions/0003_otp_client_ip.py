"""OTP challenges remember the client IP (per-IP send limit)."""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE otp_challenges ADD COLUMN client_ip text")
    op.execute("CREATE INDEX otp_challenges_ip ON otp_challenges (client_ip, last_sent_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS otp_challenges_ip")
    op.execute("ALTER TABLE otp_challenges DROP COLUMN IF EXISTS client_ip")
