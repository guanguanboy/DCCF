import argparse
from logging import LogRecord
import sys

sys.path.insert(0, '.')

import torch
import os
from pathlib import Path
from albumentations import Resize, NoOp
from iharm.data.hdataset import HDatasetUpsample
from iharm.data.transforms import HCompose, LongestMaxSizeIfLarger
from iharm.inference.predictor_upsample_hsl import PredictorUpsampleHSL
from iharm.inference.predictor_upsample_hsl_nobackbone import PredictorUpsampleHSLNoBackbone
from iharm.inference.evaluation import evaluate_dataset_upsample_hsl_refine
from iharm.inference.metrics import MetricsHub, MSE, fMSE,SSIM, PSNR, N, AvgPredictTime, COS
from iharm.inference.utils import load_model, find_checkpoint
from iharm.mconfigs import ALL_MCONFIGS
from iharm.utils.exp import load_config_file
from iharm.utils.log import logger, add_new_file_output_to_logger


RESIZE_STRATEGIES = {
    'None': NoOp(),
    'LimitLongest1024': LongestMaxSizeIfLarger(1024),
    'Fixed256': Resize(256, 256),
    'Fixed512': Resize(512, 512),
    'Fixed1024':Resize(1024,1024)
}


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('model_type', choices=ALL_MCONFIGS.keys())
    parser.add_argument('checkpoint', type=str,
                        help='The path to the checkpoint. '
                             'This can be a relative path (relative to cfg.MODELS_PATH) '
                             'or an absolute path. The file extension can be omitted.')
    parser.add_argument('--datasets', type=str, default='HFlickr,HDay2Night,HCOCO,HAdobe5k',
                        help='Each dataset name must be one of the prefixes in config paths, '
                             'which look like DATASET_PATH.')
    parser.add_argument('--resize-strategy', type=str, choices=RESIZE_STRATEGIES.keys(), default='Fixed256')
    parser.add_argument('--use-flip', action='store_true', default=False,
                        help='Use horizontal flip test-time augmentation.')
    parser.add_argument('--gpu', type=str, default=0, help='ID of used GPU.')
    parser.add_argument('--config-path', type=str, default='./config.yml',
                        help='The path to the config file.')

    parser.add_argument('--eval-prefix', type=str, default='')
    parser.add_argument('--vis-dir', type=str, default=None, help='output dir of visualization')
    parser.add_argument('--version', type=str, default='v1', help='[v1, hsl]')
    parser.add_argument('--res', type=str, default='HR', help='[HR, LR]')

    args = parser.parse_args()
    cfg = load_config_file(args.config_path, return_edict=True)
    return args, cfg


def main():
    args, cfg = parse_args()
    print(cfg.MODELS_PATH, args.checkpoint)
    cfg.MODELS_PATH = ''
    checkpoint_path = find_checkpoint(cfg.MODELS_PATH, args.checkpoint)
    add_new_file_output_to_logger(
        logs_path=Path(cfg.EXPS_PATH) / 'evaluation_logs',
        prefix=f'{Path(checkpoint_path).stem}_',
        only_message=True
    )
    logger.info(vars(args))

    device = torch.device(f'cuda:{args.gpu}')
    net = load_model(args.model_type, checkpoint_path, verbose=False)
    if args.version == 'hsl':
        predictor = PredictorUpsampleHSL(net, device, with_flip=args.use_flip)
    elif args.version == 'hsl_nobb':
        predictor = PredictorUpsampleHSLNoBackbone(net, device, with_flip=args.use_flip)

    datasets_names = args.datasets.split(',')
    datasets_metrics_low = []
    datasets_metrics_full = []


    aug_fullres = HCompose([Resize(768, 1024)])
    if args.res == 'LR':
        aug_fullres = None

    if args.vis_dir:
        try:
            os.makedirs(args.vis_dir)
        except:
            pass

    for dataset_indx, dataset_name in enumerate(datasets_names):

        dataset = HDatasetUpsample(
            cfg.get(f'{dataset_name.upper()}_PATH'), split='test', blur_target=False,
            augmentator_1=aug_fullres,
            augmentator_2=HCompose([RESIZE_STRATEGIES[args.resize_strategy]]),
            keep_background_prob=-1,
            use_hr=True,
        )

        dataset_metrics_lowres = MetricsHub([N(), MSE(), PSNR(), fMSE(), SSIM(), AvgPredictTime()],
                                     name=dataset_name)
        dataset_metrics_fullres = MetricsHub([N(), MSE(), PSNR(),fMSE(), SSIM(), AvgPredictTime()],
                                     name=dataset_name)

        evaluate_dataset_upsample_hsl_refine(dataset, predictor, dataset_metrics_lowres, dataset_metrics_fullres, visdir=args.vis_dir)

        datasets_metrics_low.append(dataset_metrics_lowres)
        datasets_metrics_full.append(dataset_metrics_fullres)

        if dataset_indx == 0:
            logger.info(dataset_metrics_lowres.get_table_header())

        if args.res == 'LR':
            logger.info(dataset_metrics_lowres)
        elif args.res == 'HR':
            logger.info(dataset_metrics_fullres)


    if len(datasets_metrics_low) > 0:

        if args.res == 'LR':
            overall_metrics = sum(datasets_metrics_low, MetricsHub([], 'Overall_low_res'))
            logger.info('-' * len(str(overall_metrics)))
            logger.info(overall_metrics)
        elif args.res == 'HR':
            overall_metrics = sum(datasets_metrics_full, MetricsHub([], 'Overall_full_res'))
            logger.info('-' * len(str(overall_metrics)))
            logger.info(overall_metrics)
        


if __name__ == '__main__':
    main()
