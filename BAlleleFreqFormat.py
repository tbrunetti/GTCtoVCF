from vcf.parser import _Format
from IlluminaBeadArrayFiles import RefStrand
import numpy as np

REVERSE_COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G", "I": "I", "D": "D"}

def extract_alleles_from_snp_string(snp_string):
    """
    Splits SNP string into tuple of individual alleles

    Args: snp_string (string): allele string of the format
        [T/C] or [G/C]

    Returns:
         allele1 (string), allele2 (string)
    """
    (allele1, allele2) = snp_string[1:4].split("/")
    assert allele1 in REVERSE_COMPLEMENT, "allele %r is invalid (expected A,T,G,C,I,D)" % allele1
    assert allele2 in REVERSE_COMPLEMENT, "allele %r is invalid (expected A,T,G,C,I,D)" % allele2
    return allele1, allele2


def extract_reverse_complement_alleles_from_snp_string(snp_string):
    """
    Splits SNP string into tuple of individual alleles and
    gets takes the reverse compliment to match strand 1

    Args: snp_string (string): allele string of the format
        [T/C] or [G/C]

    Returns:
         allele1 (string), allele2 (string)
    """
    # get alleles as tuple
    allele1, allele2 = extract_alleles_from_snp_string(snp_string)
    # get reverse compliment of bases and return
    return REVERSE_COMPLEMENT[allele1], REVERSE_COMPLEMENT[allele2]


def convert_indel_alleles(snp_string, vcf_record):
    """
    Splits SNP string into tuple of individual alleles and
    converts to actual insertion/deletion alleles from the reference

    Args: snp_string (string): allele string of the format
        [I/D] or [D/I]

    Returns:
         allele1 (string), allele2 (string)
    """
    # get alleles as tuple, we only need allele1 because if its "I" we can assume allele2 will be "D" and vice-versa
    allele1, _ = extract_alleles_from_snp_string(snp_string)

    assert len(vcf_record.ALT) == 1, "Cannot convert indel for BAF with multiple ALT alleles"
    alt_allele = str(vcf_record.ALT[0])
    ref_allele = vcf_record.REF
    # Assuming whichever sequence is smaller is the deletion and the larger is the insertion
    assert len(alt_allele) > len(ref_allele) or len(ref_allele) > len(alt_allele), "REF allele %r and ALT allele %r same length, cannot determine insertion or deletion" % (ref_allele, alt_allele)
    deletion_allele, insertion_allele = (alt_allele, ref_allele) if len(alt_allele) < len(ref_allele) else (ref_allele, alt_allele)
    if allele1 == "I":
        return insertion_allele, deletion_allele
    return deletion_allele, insertion_allele

class BAlleleFreqFormat(object):
    """
    Generate b allele frequency format information for VCF
    """
    def __init__(self, logger, b_allele_freq):
        self._b_allele_freq = b_allele_freq
        self._logger = logger

    @staticmethod
    def get_id():
        return "BAF"

    @staticmethod
    def get_description():
        return "B Allele Frequency"

    @staticmethod
    def get_format_obj():
        # arguments should be: ['id', 'num', 'type', 'desc']
        return _Format(BAlleleFreqFormat.get_id(), 1, "Float", BAlleleFreqFormat.get_description())

    def generate_sample_format_info(self, bpm_records, vcf_record, sample_name):
        """
        Get the sample B allele frequency

        Args:

        Returns:
            float: B allele frequency
        """
        # if we have more than 1 BPMRecord, need to merge
        b_allele_freq_list = []
        # if we have more than 1 alt allele, return missing
        if len(vcf_record.ALT) > 1:
            return "."
        for i in range(len(bpm_records)):
            bpm_record = bpm_records[i]
            snp = bpm_record.snp
            strand = bpm_record.ref_strand
            idx = bpm_record.index_num
            b_allele_freq = self._b_allele_freq[idx]

            # if indel, convert to actual ref and alt sequences
            if bpm_record.is_indel():
                allele1, allele2 = convert_indel_alleles(snp, vcf_record)
            # if  2/minus strand, get rev comp
            elif strand == RefStrand.Minus:
                allele1, allele2 = extract_reverse_complement_alleles_from_snp_string(snp)
            else:
                allele1, allele2 = extract_alleles_from_snp_string(snp)

            # normalize to reference allele
            ref_allele = vcf_record.REF
            assert allele1 == ref_allele or allele2 == ref_allele, "allele1: %r or allele2 %r do not match ref: %r" % (allele1, allele2, ref_allele)
            # if allele1 is reference, then B allele is correct
            if allele1 == ref_allele:
                b_allele_freq_list.append(b_allele_freq)
            # if allele2 is reference, then we need to do 1-freq
            else:
                b_allele_freq_list.append(1. - b_allele_freq)

        # nanmedian ignores NaN values
        final_b_allele_freq = np.nanmedian(b_allele_freq_list)
        if np.isnan(final_b_allele_freq):
            return "."
        else:
            return final_b_allele_freq
