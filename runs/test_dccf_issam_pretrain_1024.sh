weights="pretrained_models/dccf_issam_HR_pretrain.pth"
CUDA_VISIBLE_DEVICES=1 python3 scripts/evaluate_upsample_refiner.py dccf_improved_ssam256_HR_clamp ${weights} \
    --resize-strategy Fixed1024 \
    --version hsl_nobb \
    --config-path config_test_adobe1024.yml \
    --datasets HAdobe5k \
    --vis-dir \
    /data1/liguanlin/codes/research_projects/DCCF/results/1024        