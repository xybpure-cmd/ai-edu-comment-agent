from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Any
@dataclass
class NewsItem:
    id:str; title:str; url:str; source_level:str; content_type:str; summary:str
@dataclass
class Candidate:
    id:str; news_item_id:str; priority_score:int; recommended:bool; eligible_for_formal_pack:bool; hold_reason:str=''
@dataclass
class TopicCard:
    id:str; topic_name:str; topic_type:str; description:str; related_items:list[str]; trend_note:str; status:str; priority_level:str='medium'; watch_reason:str=''; history:list[dict[str,Any]]=field(default_factory=list)
    def to_dict(self)->dict[str,Any]: return asdict(self)
@dataclass
class CommentPack:
    id:str; candidate_id:str; status:str; hold_reason:str; basic_info:dict[str,Any]; one_sentence_summary:str; verified_facts:list[str]; pending_checks:list[str]; comment_value:str; angle_options:list[str]; author_judgement_seed:str; short_comment:str; long_comment:str; sources:list[dict[str,Any]]; author_decision_points:list[str]; planning:dict[str,Any]=field(default_factory=dict); recommended_title_options:list[str]=field(default_factory=list); opening_hook_options:list[str]=field(default_factory=list); key_claims:list[str]=field(default_factory=list); possible_counterarguments:list[str]=field(default_factory=list); primary_title:str=''; alternative_titles:list[str]=field(default_factory=list); suggested_opening_paragraph:str=''; ending_suggestion:str=''
    def to_dict(self)->dict[str,Any]: return asdict(self)
