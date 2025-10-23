import logging

from app.models import Claim, QuantifierOp, QuantifierType
from app.services.llm import llm_service

logger = logging.getLogger(__name__)


class ClaimValidator:
    def validate_quantifiers(self, search_claim: Claim, matched_quantifiers: list[dict]) -> bool:
        if not search_claim.quantifiers:
            return True

        if not matched_quantifiers:
            return True

        for search_q in search_claim.quantifiers:
            matched_q_for_noun = None
            for mq in matched_quantifiers:
                if mq.get("qtype") == search_q.qtype.value and mq.get("noun") == search_q.noun:
                    matched_q_for_noun = mq
                    break

            if not matched_q_for_noun:
                continue

            matched_vmin = matched_q_for_noun.get("vmin")
            matched_vmax = matched_q_for_noun.get("vmax")

            if matched_vmin is None or matched_vmax is None:
                continue

            is_valid = False
            
            if search_q.op == QuantifierOp.GTE:
                is_valid = matched_vmin >= search_q.vmin
            elif search_q.op == QuantifierOp.LTE:
                is_valid = matched_vmax <= search_q.vmax
            elif search_q.op == QuantifierOp.GT:
                is_valid = matched_vmin > search_q.vmin
            elif search_q.op == QuantifierOp.LT:
                is_valid = matched_vmax < search_q.vmax
            elif search_q.op == QuantifierOp.EQUALS:
                is_valid = matched_vmin <= search_q.vmin <= matched_vmax
            elif search_q.op == QuantifierOp.RANGE:
                is_valid = not (matched_vmax < search_q.vmin or matched_vmin > search_q.vmax)
            elif search_q.op == QuantifierOp.APPROX:
                is_valid = matched_vmin <= search_q.vmin <= matched_vmax
            
            if not is_valid:
                logger.info(
                    f"Quantifier mismatch: search wants {search_q.noun} {search_q.op.value} {search_q.vmin}-{search_q.vmax}, "
                    f"indexed has {matched_vmin}-{matched_vmax}"
                )
                return False

        return True
    
    def validate_count_quantifiers(self, search_claim: Claim, matched_quantifiers: list[dict]) -> bool:
        if not search_claim.quantifiers:
            return True

        search_count_quantifiers = [q for q in search_claim.quantifiers if q.qtype == QuantifierType.COUNT]

        if not search_count_quantifiers:
            return True
        
        return self.validate_quantifiers(search_claim, matched_quantifiers)

    async def validate_all_claim_pairs(self, best_matches: dict) -> dict[tuple[str, str], str]:
        pairs_list = [(match["search_claim"], match["matched_claim"]) for match in best_matches.values()]
        logger.info(f"Validating {len(pairs_list)} unique claim pairs (global best matches)")
        return await llm_service.validate_claim_compatibility_batch(pairs_list)


claim_validator = ClaimValidator()

