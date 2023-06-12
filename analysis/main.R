library(tidyverse)
library(psych)
library(effsize)
library(effects)

library(Rfast)

PREPROCESSING_PATH <- file.path("..", "preprocessing")
DATA_DIR <- file.path(PREPROCESSING_PATH, "output")
EXCLUSION_DIR <- file.path(PREPROCESSING_PATH, "exclusion")

inlab <- read.csv('inlab_data.csv', stringsAsFactors = TRUE)

general_exclusions <- read.csv(file.path(EXCLUSION_DIR, '_exclusions_general.csv'))

webgazer <- read.csv(file.path(DATA_DIR, 'webgazer_data.csv'))
webgazer_resampled <- read.csv(file.path(DATA_DIR, 'webgazer_RESAMPLED_data.csv'))
webgazer_validate <- read.csv(file.path(DATA_DIR, 'webgazer_validation.csv'))
webgazer_exclusions <- read.csv(file.path(EXCLUSION_DIR, 'exclusions_webgazer.csv'))

icatcher <- read.csv(file.path(DATA_DIR, 'icatcher_data.csv'))
icatcher_resampled <- read.csv(file.path(DATA_DIR, 'icatcher_RESAMPLED_data.csv'))
icatcher_exclusions <- read.csv(file.path(EXCLUSION_DIR, 'exclusions_icatcher.csv'))

icatcher_validate <- icatcher %>% filter(stimulus == 'calibration')
icatcher_data <- icatcher %>% filter(stimulus != 'calibration')
icatcher_data_resampled <- icatcher_resampled %>% filter(stimulus != 'calibration')


# TODO: describe sample
# TODO: turn into rmd 
# mutate(id = str_remove(id, "_B"),
# id = str_remove(id, "_A"))%>%

#####################
# Exclusion reporting
#####################

### General - applies to all trackers

apply_exclusion_reason = function(df, reason){
  next_df <- df %>% filter(exclusion_reason != reason)
  print(sprintf("Excluded Trials due to %s: %i", reason, nrow(df)-nrow(next_df)))
  participant_diff = length(unique(df$id)) - length(unique(next_df$id))
  if(participant_diff > 0){
    print(sprintf("Exclusion due to %s leads to: %i participants having no more remaining trials", reason, participant_diff))
  }
  return(next_df)
}

print_exclusions_for_tracker = function(name, df, reasons){
  exclusions_trials <- df %>% filter(stimulus != 'validation1' & stimulus != 'validation2' & stimulus != 'calibration')
  print(sprintf("%s EXCLUSIONS:", name))
  for(reason in reasons){
    exclusions_trials <- apply_exclusion_reason(exclusions_trials, reason)
  }
  print(sprintf("Remaining participants for %s: %i", name, length(unique(exclusions_trials$id))))
  print(sprintf("Remaining trials for %s: %i", name, nrow(exclusions_trials)))
  print('------')
}

# Total number of participants
length(unique(general_exclusions$id))

print_exclusions_for_tracker('GENERAL',general_exclusions,c('all_age', 'all_preterm', 'all_nonormalseeing', 'all_experimentererror', 'all_nodata', 'nodata', 'unattentive'))
print_exclusions_for_tracker('WEBGAZER',webgazer_exclusions,c('_low_sampling_wg', '_no_tracker_data', 'parentgaze_wg', 'tracking_wg'))
print_exclusions_for_tracker('ICATCHER',icatcher_exclusions,c('wrongwebcam_ic', 'noface_ic'))


#################
# Preprocessing
##################

CRITICAL_TIMEFRAME_START_MS = 25900
CRITICAL_TIMEFRAME_DURATION_MS = 4000

exctract_lookingscore_per_timepoint = function(resampled_data){
  return(resampled_data %>%
    group_by(t) %>% 
    summarize(lookingscore = sum(grepl("target", hit, fixed = TRUE), na.rm = TRUE) / sum(grepl("target", hit, fixed = TRUE) | grepl( "distractor", hit, fixed = TRUE)))
  )
}

exctract_lookingscore_critical = function(data){
  
  ls_by_trial <- data %>%
    filter(CRITICAL_TIMEFRAME_START_MS <= t & t <= CRITICAL_TIMEFRAME_START_MS + CRITICAL_TIMEFRAME_DURATION_MS) %>%
    group_by(id, stimulus)%>%
    summarize(lookingscore = sum(grepl("target", hit, fixed = TRUE), na.rm = TRUE) / sum(grepl("target", hit, fixed = TRUE) | grepl( "distractor", hit, fixed = TRUE)),
              trial = first(trial))
  
  ls_by_part <- ls_by_trial %>% 
    group_by(id) %>%
    summarize(lookingscore = mean(lookingscore))
  
  return(list("by_trial" = ls_by_trial, "by_participant" = ls_by_part))
}

webgazer_aoi <- webgazer %>% mutate(hit=aoi_hit)
webgazer_side <- webgazer %>% mutate(hit=side_hit)

webgazer_aoi_resampled <- webgazer_resampled %>% mutate(hit=aoi_hit)
webgazer_side_resampled <- webgazer_resampled %>% mutate(hit=side_hit)

webgazer_aoi_ls_crit <- exctract_lookingscore_critical(webgazer_aoi)
webgazer_side_ls_crit <- exctract_lookingscore_critical(webgazer_side)

icatcher_ls_crit <- exctract_lookingscore_critical(icatcher_data)

# because some labs used exactly the same id
inlab$id <- paste0(inlab$subid, "_", inlab$lab)

inlab_ls_by_trial <- inlab %>%
  filter(experiment_num=="pilot_1a" & t >= -4000 & t <= 0) %>%
  mutate(stimulus = substr(stimulus, 1, 6)) %>%
  group_by(id, stimulus) %>%
  summarize(lookingscore = sum(grepl("target", aoi, fixed = TRUE), na.rm = TRUE) / sum(grepl("target", aoi, fixed = TRUE) | grepl( "distractor", aoi, fixed = TRUE)),
            trial = first(trial_num) 
  ) %>%
  ungroup() %>% 
  na.omit() #%>% 
#mutate(lookingscore = round(lookingscore, digits=2))

inlab_ls_by_participant <- inlab_ls_by_trial %>% 
  group_by(id) %>%
  summarize(lookingscore = mean(lookingscore))


inlab_ls_by_trial$method <- "inlab"
webgazer_aoi_ls_crit$by_trial$method <- "webgazer_aoi"
icatcher_ls_crit$by_trial$method <- "icatcher"

full_data <- inlab_ls_by_trial %>% rbind(webgazer_aoi_ls_crit$by_trial) %>% rbind(icatcher_ls_crit$by_trial)

full_data_by_participant <- full_data %>% group_by(id, method) %>% summarise(lookingscore = mean(lookingscore))

data <- full_data_by_participant %>%
  mutate(method = factor(method, levels = c("webgazer_aoi", "icatcher", "inlab")))


#table(icatcher_ls_crit$by_trial$stimulus)
 
###########################
# Confirmatory Analyses
#########################

test_goal_based_prediction = function(name, values){
  print('____')
  print(name)
  print(t.test(values, mu = 0.5, alternative = "two.sided"))
  print(effsize::cohen.d(values,f=NA, mu = 0.5))
  print('____')
}

test_goal_based_prediction('wg aoi by trial', webgazer_aoi_ls_crit$by_trial$lookingscore)
test_goal_based_prediction('wg aoi by participant', webgazer_aoi_ls_crit$by_participant$lookingscore)

test_goal_based_prediction('wg side by trial', webgazer_side_ls_crit$by_trial$lookingscore)
test_goal_based_prediction('wg side by participant', webgazer_side_ls_crit$by_participant$lookingscore)

test_goal_based_prediction('icatcher by trial', icatcher_ls_crit$by_trial$lookingscore)
test_goal_based_prediction('icatcher by participant', icatcher_ls_crit$by_participant$lookingscore)


## Compare to in lab sample (TODO: think again about what to test here)

h2 <- lm(lookingscore ~ method, data)
anova(h2)
summary(h2)
plot(allEffects(h2))


####################################
## Calculate agreement between webgazer and icatcher
#####################################

agreement_raw <- webgazer_resampled %>% mutate(aoi_wg = aoi, side_wg = side) %>% 
  inner_join(icatcher_data_resampled %>% mutate(side_ic = look), by=c('id','stimulus','t')) %>% 
  select(id, stimulus, t, aoi_wg, side_wg, side_ic) 

# code left and right so that they can be used for binary agreement measures
agreement_raw <- agreement_raw %>% mutate_at(vars(c('aoi_wg','side_wg','side_ic')), ~ifelse(.=='left', 1, ifelse(.=='right', 0, .)))


# exclude all timepoints where any of the trackers did not produce a value
agreement_raw[agreement_raw==''] <- NA
agreement_raw <- agreement_raw %>% na.omit()


# exclude timepoints before the critical window - icatcher only knows left vs right and there was no clearly expected side to look at
agreement_raw_after_critical_start <- agreement_raw %>% filter(CRITICAL_TIMEFRAME_START_MS <= t)

# exclude timepoints where icatcher did not decide on a side
agreement_after_critical_start <- agreement_raw_after_critical_start %>%  filter(side_ic != 'none' & side_ic != 'away' & side_ic != 'nobabyface' & side_ic != 'noface')


# how much general agreement?

agreement_in_critical <- agreement_after_critical_start %>% filter(t <= CRITICAL_TIMEFRAME_START_MS + CRITICAL_TIMEFRAME_DURATION_MS)
agreement_after_critical_end <- agreement_after_critical_start %>% filter(t >= CRITICAL_TIMEFRAME_START_MS + CRITICAL_TIMEFRAME_DURATION_MS)

psych::cohen.kappa(x=cbind(agreement_after_critical_start$side_wg,agreement_after_critical_start$side_ic))
col.yule(as.numeric(agreement_after_critical_start$side_wg), as.numeric(agreement_after_critical_start$side_ic))

psych::cohen.kappa(x=cbind(agreement_in_critical$side_wg,agreement_in_critical$side_ic))
col.yule(as.numeric(agreement_in_critical$side_wg), as.numeric(agreement_in_critical$side_ic))

psych::cohen.kappa(x=cbind(agreement_after_critical_end$side_wg,agreement_after_critical_end$side_ic))
col.yule(as.numeric(agreement_after_critical_end$side_wg), as.numeric(agreement_after_critical_end$side_ic))


# when webgazer hit aoi, did icatcher agree?
agreement_aoi_after_critical_start <- agreement_after_critical_start %>%  filter(aoi_wg != 'none')

agreement_aoi_in_critical <- agreement_aoi_after_critical_start %>% filter(t <= CRITICAL_TIMEFRAME_START_MS + CRITICAL_TIMEFRAME_DURATION_MS)
agreement_aoi_after_critical_end <- agreement_aoi_after_critical_start %>% filter(t >= CRITICAL_TIMEFRAME_START_MS + CRITICAL_TIMEFRAME_DURATION_MS)

psych::cohen.kappa(x=cbind(agreement_aoi_after_critical_start$side_wg,agreement_aoi_after_critical_start$side_ic))
col.yule(as.numeric(agreement_aoi_after_critical_start$side_wg), as.numeric(agreement_aoi_after_critical_start$side_ic))

psych::cohen.kappa(x=cbind(agreement_aoi_in_critical$side_wg,agreement_aoi_in_critical$side_ic))
col.yule(as.numeric(agreement_in_critical$side_wg), as.numeric(agreement_in_critical$side_ic))

psych::cohen.kappa(x=cbind(agreement_aoi_after_critical_end$side_wg,agreement_aoi_after_critical_end$side_ic))
col.yule(as.numeric(agreement_aoi_after_critical_end$side_wg), as.numeric(agreement_aoi_after_critical_end$side_ic))


###########################
## Validation?
###########################

## WebGazer 

mean_offset_x_percent <- mean(abs(webgazer_validate$avg_offset_x_percent))
sd_offset_x_percent <- sd(abs(webgazer_validate$avg_offset_x_percent))
mean_offset_y_percent <- mean(abs(webgazer_validate$avg_offset_y_percent))
sd_offset_y_percent <- sd(abs(webgazer_validate$avg_offset_y_percent))

deterioration <- webgazer_validate %>%  
  pivot_wider(names_from = index, values_from = -c(index, id)) %>% 
  mutate(y_det = abs(avg_offset_y_percent_1) - abs(avg_offset_y_percent_0),
         x_det = abs(avg_offset_x_percent_1) - abs(avg_offset_x_percent_0)) %>%  
  select(id, y_det, x_det)


cohens_delta_x <- mean(deterioration$x_det) / sd(deterioration$x_det)
t.test(deterioration$x_det, mu = 0, alternative = "two.sided")

cohens_delta_y <- mean(deterioration$y_det) / sd(deterioration$y_det)
t.test(deterioration$y_det, mu = 0, alternative = "two.sided")

## ICatcher
RILAKUMA_LEFT_START <- 6500
RILAKUMA_LEFT_END <- 15150
RILAKUMA_RIGHT_START <- 18700

calibration_hits <- icatcher_validate %>% 
  mutate(rilakuma_side = ifelse(RILAKUMA_LEFT_START <= t & t <= RILAKUMA_LEFT_END,
                                'left',
                                ifelse(RILAKUMA_RIGHT_START <= t,
                                       'right', 
                                       'none')
                                )
         ) %>% 
  filter((rilakuma_side == 'left' | rilakuma_side == 'right') & (look == 'left' | look == 'right')) %>% 
  mutate(hit = ifelse(rilakuma_side == look,1,0)) %>% 
  select(id, t, look, hit)

calibration_hits_per_part <- calibration_hits %>% group_by(id) %>% summarize(score=mean(hit))

mean(calibration_hits$hit)


######################
# Visualizations
#####################

## plot lookingscore over time for webcam based methods

webgazer_aoi_ls_over_time <- exctract_lookingscore_per_timepoint(webgazer_aoi_resampled) %>% mutate(tracker='webgazer_aoi')
webgazer_side_ls_over_time <- exctract_lookingscore_per_timepoint(webgazer_side_resampled) %>% mutate(tracker='webgazer_side')
icatcher_ls_over_time <- exctract_lookingscore_per_timepoint(icatcher_data_resampled) %>% mutate(tracker='icatcher')

ls_over_time <- do.call("rbind", list(
  webgazer_aoi_ls_over_time,
  webgazer_side_ls_over_time, 
  icatcher_ls_over_time
)) %>% spread(key = tracker, value = lookingscore)


plot(ls_over_time$t, ls_over_time$icatcher, type = "l")
plot(ls_over_time$t, ls_over_time$webgazer_side, type = "l")
plot(ls_over_time$t, ls_over_time$webgazer_aoi, type = "l")


## Plot difference in lookinscore between methods 

errorbars <- data %>% group_by(method) %>%
  summarise(mean = mean(lookingscore), se = 1.96*sd(lookingscore)/sqrt(n()), upper = mean + se, lower = mean - se)

# plot the data
H2.plot <- ggplot(data, aes(x = method, y = lookingscore, colour = method, fill = method)) +
  geom_violin(alpha = 0.5, width = 1, position = position_dodge(width = 0.9), show.legend = FALSE ) +
  geom_jitter(aes(colour = method),  size = 2, alpha = 0.6, position = position_jitterdodge(jitter.width = 0.2, jitter.height = 0, dodge.width = 0.9), show.legend = FALSE) +
  geom_point(aes(x = method, y = mean), errorbars, inherit.aes = FALSE, size = 2, color = "black") +
  geom_errorbar(aes(x = method, ymax = upper, ymin = lower), errorbars, inherit.aes = FALSE,
                stat = "identity", width = 0.05, color = "black") +
  ylim(0, 1) +
  scale_colour_manual(values=c("skyblue", "red", "green"))  +
  scale_fill_manual(values=c("skyblue",  "red", "green")) +
  geom_hline(yintercept=0.5, linetype="dashed", color = "black") +
  labs(title="Proportion Looking Score per method (95% CIs)", x="Method", y="Proportion Looking Score (target/target+distractor)") +
  theme_classic()

print(H2.plot)



