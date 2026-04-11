from pydantic import BaseModel


class AllNewsReq(BaseModel):
    pass


class AllNewsRes(BaseModel):
    news_links: list[str]


class NewsReq(BaseModel):
    link: str


class NewsRes(BaseModel):
    title: str
    content: str
