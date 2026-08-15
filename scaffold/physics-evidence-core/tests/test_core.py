from physics_evidence_core import KnowledgeFreeze, PredictionRecord, HeldOutObservation, LeakageViolation, compare_held_out, create_certificate, verify_certificate

def test_holdout_and_certificate():
    freeze=KnowledgeFreeze("f1","2003-12-31",("a"*64,),frozenset({"Z1-N1"}),("b"*64,),"features-v1")
    pred=PredictionRecord("Z2-N2","mass_excess_keV",1.0,0.2,"m1","f1")
    truth=HeldOutObservation("Z2-N2","mass_excess_keV",1.1,"b"*64,"later")
    comp=compare_held_out(pred,truth,freeze)
    assert comp.held_out_reused_in_fit is False
    cert=create_certificate({"certificate_version":"1","prediction_id":pred.prediction_id,
        "subject_id":pred.subject_id,"observable":pred.observable,"knowledge_freeze_id":"f1",
        "training_ids_sha256":freeze.training_ids_sha256,"model_id":"m1","prediction_mean":1.0,
        "prediction_std":0.2,"uncertainty_scope":"test"})
    assert verify_certificate(cert)

def test_leakage_target_in_training_fails():
    freeze=KnowledgeFreeze("f1","2003-12-31",("a"*64,),frozenset({"Z2-N2"}),(),"f")
    pred=PredictionRecord("Z2-N2","mass_excess_keV",1.0,None,"m","f1")
    truth=HeldOutObservation("Z2-N2","mass_excess_keV",1.1,"b"*64,"later")
    try: compare_held_out(pred,truth,freeze)
    except LeakageViolation: pass
    else: raise AssertionError("expected LeakageViolation")
