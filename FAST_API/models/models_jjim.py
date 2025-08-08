from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from db import Base


class Jjim(Base):
    __tablename__ = "jjim"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_jjim_user_product"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)

    user = relationship("models.models_auth.User")


